"""Who owes us money — and the bug that hid half the answer.

Two things are covered here:

1. **A regression I introduced.** When the HĐNT path was added, an order could
   be agreed via an ĐƠN ĐẶT HÀNG instead of a Contract. But `sales()`,
   `top_customers` and `accounting()` each had their OWN copy of "booked
   revenue = signed contracts", so all three kept counting only contracts.
   Every framework-agreement order contributed ZERO to booked value and to
   receivable — the business under-reported what it was owed.

2. **G4.** The receivable figure said how much was owed but never BY WHOM, so
   chasing debt could not be done from the system, while the supplier side
   already answered the mirror question.
"""
import datetime as dt

import pytest

from app.services.report_service import ReportService


@pytest.fixture()
def two_customers(app, seed):
    """One customer agreed via Contract, one via ĐƠN ĐẶT HÀNG."""
    from app.config import db
    from app.models import Customer, Order
    from app.models.models import (
        Contract, LifecycleStatus, MasterAgreement, OrderConfirmation,
    )

    with app.app_context():
        # --- customer A: ordinary signed contract, 10,000,000 -------------
        a = Customer(company_id=seed["company_id"], store_id=seed["store_id"],
                     customer_code="KH-A", name="Khach Hop Dong")
        b = Customer(company_id=seed["company_id"], store_id=seed["store_id"],
                     customer_code="KH-B", name="Khach HDNT")
        db.session.add_all([a, b])
        db.session.flush()

        oa = Order(company_id=seed["company_id"], store_id=seed["store_id"],
                   customer_id=a.id, order_code="ORD-A", title="A")
        ob = Order(company_id=seed["company_id"], store_id=seed["store_id"],
                   customer_id=b.id, order_code="ORD-B", title="B")
        db.session.add_all([oa, ob])
        db.session.flush()
        db.session.add_all([LifecycleStatus(order_id=oa.id),
                            LifecycleStatus(order_id=ob.id)])

        db.session.add(Contract(
            company_id=seed["company_id"], order_id=oa.id,
            contract_number="CT-A", contract_date=dt.date(2026, 1, 1),
            contract_value=10_000_000, is_signed=True))

        # --- customer B: agreed via a framework agreement, 20,000,000 -----
        ma = MasterAgreement(
            company_id=seed["company_id"], customer_id=b.id,
            agreement_number="HDNT-R", effective_from=dt.date(2026, 1, 1),
            status=MasterAgreement.STATUS_ACTIVE)
        db.session.add(ma)
        db.session.flush()
        db.session.add(OrderConfirmation(
            company_id=seed["company_id"], order_id=ob.id,
            master_agreement_id=ma.id, confirmation_number="DDH-R",
            confirmation_date=dt.date(2026, 1, 2),
            total_amount=20_000_000,
            status=OrderConfirmation.STATUS_CONFIRMED))

        db.session.commit()
        return {'a_id': str(a.id), 'b_id': str(b.id),
                'order_a': str(oa.id), 'order_b': str(ob.id), **seed}


# --- the regression -------------------------------------------------------

def test_booked_value_counts_framework_agreement_orders(app, two_customers):
    """A DDH order used to contribute nothing at all."""
    with app.app_context():
        result = ReportService().sales(two_customers["company_id"])
        assert result['booked_value'] == 30_000_000, (
            "booked value must include the 20,000,000 agreed via DDH, not only "
            "the 10,000,000 agreed via a signed contract"
        )


def test_receivable_counts_framework_agreement_orders(app, two_customers):
    with app.app_context():
        result = ReportService().accounting(two_customers["company_id"])
        assert result['booked_value'] == 30_000_000
        assert result['receivable'] == 30_000_000


def test_a_framework_customer_appears_in_top_customers(app, two_customers):
    """They were invisible in the ranking while counted in the total."""
    with app.app_context():
        names = {c['name'] for c in
                 ReportService().sales(two_customers["company_id"])['top_customers']}
        assert 'Khach HDNT' in names


def test_an_unconfirmed_confirmation_is_not_counted(app, two_customers):
    """Only a CONFIRMED order confirmation is an agreement."""
    from app.config import db
    from app.models.models import OrderConfirmation

    with app.app_context():
        conf = OrderConfirmation.query.filter_by(confirmation_number="DDH-R").first()
        conf.status = OrderConfirmation.STATUS_DRAFT
        db.session.commit()

        assert ReportService().sales(
            two_customers["company_id"])['booked_value'] == 10_000_000


def test_a_cancelled_confirmation_is_not_counted(app, two_customers):
    from app.config import db
    from app.models.models import OrderConfirmation

    with app.app_context():
        conf = OrderConfirmation.query.filter_by(confirmation_number="DDH-R").first()
        conf.is_canceled = True
        db.session.commit()

        assert ReportService().sales(
            two_customers["company_id"])['booked_value'] == 10_000_000


# --- G4: who owes us -----------------------------------------------------

def test_receivables_are_listed_per_customer(app, two_customers):
    with app.app_context():
        rows = ReportService().customer_receivables(two_customers["company_id"])
        by_name = {r['customer_name']: r for r in rows}

        assert by_name['Khach Hop Dong']['outstanding'] == 10_000_000
        assert by_name['Khach HDNT']['outstanding'] == 20_000_000


def test_a_payment_reduces_only_that_customer_balance(app, two_customers):
    from app.config import db
    from app.models.models import PaymentReport

    with app.app_context():
        db.session.add(PaymentReport(
            company_id=two_customers["company_id"],
            order_id=two_customers["order_a"], report_number="PM-A",
            report_date=dt.date(2026, 2, 1), payment_date=dt.date(2026, 2, 1),
            payment_type='advance', amount=4_000_000,
            advance_amount=4_000_000, is_confirmed=True))
        db.session.commit()

        rows = {r['customer_name']: r for r in
                ReportService().customer_receivables(two_customers["company_id"])}
        assert rows['Khach Hop Dong']['outstanding'] == 6_000_000
        assert rows['Khach HDNT']['outstanding'] == 20_000_000, \
            "another customer's payment must not reduce this balance"


def test_the_biggest_debt_is_listed_first(app, two_customers):
    """The list is a work queue: chase the largest first."""
    with app.app_context():
        rows = ReportService().customer_receivables(two_customers["company_id"])
        assert rows[0]['customer_name'] == 'Khach HDNT'


def test_a_fully_paid_customer_is_marked_settled(app, two_customers):
    from app.config import db
    from app.models.models import PaymentReport

    with app.app_context():
        db.session.add(PaymentReport(
            company_id=two_customers["company_id"],
            order_id=two_customers["order_a"], report_number="PM-FULL",
            report_date=dt.date(2026, 2, 1), payment_date=dt.date(2026, 2, 1),
            payment_type='advance', amount=10_000_000,
            advance_amount=10_000_000, is_confirmed=True))
        db.session.commit()

        rows = {r['customer_name']: r for r in
                ReportService().customer_receivables(two_customers["company_id"])}
        assert rows['Khach Hop Dong']['settled'] is True
        assert rows['Khach Hop Dong']['outstanding'] == 0


def test_an_unconfirmed_payment_does_not_reduce_the_debt(app, two_customers):
    """Money promised is not money received."""
    from app.config import db
    from app.models.models import PaymentReport

    with app.app_context():
        db.session.add(PaymentReport(
            company_id=two_customers["company_id"],
            order_id=two_customers["order_a"], report_number="PM-UNCONF",
            report_date=dt.date(2026, 2, 1), payment_date=dt.date(2026, 2, 1),
            payment_type='advance', amount=5_000_000,
            advance_amount=5_000_000, is_confirmed=False))
        db.session.commit()

        rows = {r['customer_name']: r for r in
                ReportService().customer_receivables(two_customers["company_id"])}
        assert rows['Khach Hop Dong']['outstanding'] == 10_000_000


def test_receivables_are_tenant_scoped(app, two_customers, seed):
    from app.config import db
    from app.models import Company

    with app.app_context():
        other = Company(company_code="RCV", name="Rival", email="r@rcv.test")
        db.session.add(other)
        db.session.commit()
        assert ReportService().customer_receivables(other.id) == []
