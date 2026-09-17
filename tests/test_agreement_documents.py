"""Document variables for HĐNT and ĐƠN ĐẶT HÀNG.

The citation fields are the important ones: a reprint years later must show
what the document actually cited when it was issued, not what the agreement
says today.
"""
import datetime as dt

import pytest

from app.utils.template_engine import DocumentVariableCollector as Collector


@pytest.fixture()
def agreement(app, seed):
    from app.config import db
    from app.models.models import MasterAgreement, MasterAgreementPriceLine

    with app.app_context():
        ma = MasterAgreement(
            company_id=seed["company_id"], customer_id=seed["customer_id"],
            agreement_number="HDNT-DOC-1",
            signed_date=dt.date(2026, 1, 15),
            effective_from=dt.date(2026, 2, 1),
            effective_to=None,
            auto_renew=True, renewal_notice_days=30,
            status=MasterAgreement.STATUS_ACTIVE,
            payment_terms="Thanh toan trong 30 ngay",
            penalty_pct=8)
        db.session.add(ma)
        db.session.flush()
        # one current line and one superseded line
        db.session.add(MasterAgreementPriceLine(
            agreement_id=ma.id, product_key='sofa', product_name='Sofa 3 cho',
            unit='bo', agreed_unit_price=9_000_000,
            effective_from=dt.date(2026, 2, 1)))
        db.session.add(MasterAgreementPriceLine(
            agreement_id=ma.id, product_key='sofa', product_name='Sofa 3 cho',
            unit='bo', agreed_unit_price=8_000_000,
            effective_from=dt.date(2025, 1, 1),
            effective_to=dt.date(2026, 1, 31)))
        db.session.commit()
        return str(ma.id)


def _agreement(agreement_id):
    from app.models.models import MasterAgreement
    return MasterAgreement.query.get(agreement_id)


def test_agreement_context_carries_the_framework_terms(app, agreement, seed):
    from app.models import Customer

    with app.app_context():
        ma = _agreement(agreement)
        ctx = Collector.collect_master_agreement_variables(
            ma, Customer.query.get(seed["customer_id"]))

        assert ctx['agreement_number'] == 'HDNT-DOC-1'
        assert ctx['agreement_date'] == '15/01/2026'
        assert ctx['payment_terms'] == 'Thanh toan trong 30 ngay'
        assert ctx['penalty_pct'] == '8.0'


def test_open_ended_agreement_prints_words_not_a_blank(app, agreement, seed):
    """An empty end date is normal practice, not missing data."""
    from app.models import Customer

    with app.app_context():
        ctx = Collector.collect_master_agreement_variables(
            _agreement(agreement), Customer.query.get(seed["customer_id"]))
        assert ctx['effective_to'] == 'Vô thời hạn'


def test_auto_renew_clause_is_rendered_as_a_sentence(app, agreement, seed):
    from app.models import Customer

    with app.app_context():
        ctx = Collector.collect_master_agreement_variables(
            _agreement(agreement), Customer.query.get(seed["customer_id"]))
        assert '30 ngày' in ctx['auto_renew_text']


def test_only_current_price_lines_are_printed(app, agreement, seed):
    """A superseded price is history, not a term of the agreement."""
    from app.models import Customer

    with app.app_context():
        ctx = Collector.collect_master_agreement_variables(
            _agreement(agreement), Customer.query.get(seed["customer_id"]))

        assert ctx['has_price_list'] is True
        assert len(ctx['price_lines']) == 1, "the closed line must not be printed"
        assert ctx['price_lines'][0]['agreed_unit_price'] == '9,000,000'


# --- order confirmation --------------------------------------------------

@pytest.fixture()
def confirmation(app, seed, agreement):
    from app.config import db
    from app.models import Order
    from app.models.models import OrderConfirmation

    with app.app_context():
        order = Order(company_id=seed["company_id"], store_id=seed["store_id"],
                      customer_id=seed["customer_id"], order_code="ORD-DOC",
                      title="Doc order")
        db.session.add(order)
        db.session.flush()
        conf = OrderConfirmation(
            company_id=seed["company_id"], order_id=order.id,
            master_agreement_id=agreement,
            confirmation_number="DDH-DOC-1",
            confirmation_date=dt.date(2026, 6, 10),
            cited_agreement_number="HDNT-DOC-1",
            cited_agreement_date=dt.date(2026, 1, 15),
            items=[{'name': 'Sofa 3 cho', 'unit': 'bo', 'quantity': 2,
                    'unit_price': 9_000_000, 'total': 18_000_000}],
            subtotal=18_000_000, vat_rate=8, vat_amount=1_440_000,
            total_amount=19_440_000,
            delivery_date=dt.date(2026, 7, 1),
            payment_terms="Thanh toan trong 30 ngay")
        db.session.add(conf)
        db.session.commit()
        return {"confirmation_id": str(conf.id), "order_id": str(order.id)}


def test_confirmation_context_cites_the_agreement(app, confirmation, seed):
    from app.models import Customer, Order
    from app.models.models import OrderConfirmation

    with app.app_context():
        conf = OrderConfirmation.query.get(confirmation["confirmation_id"])
        ctx = Collector.collect_order_confirmation_variables(
            conf, Customer.query.get(seed["customer_id"]),
            Order.query.get(confirmation["order_id"]))

        assert ctx['confirmation_number'] == 'DDH-DOC-1'
        assert ctx['cited_agreement_number'] == 'HDNT-DOC-1'
        assert 'Căn cứ Hợp đồng nguyên tắc số HDNT-DOC-1' in ctx['agreement_reference_text']
        assert '15/01/2026' in ctx['agreement_reference_text']


def test_confirmation_context_carries_the_money(app, confirmation, seed):
    from app.models import Customer, Order
    from app.models.models import OrderConfirmation

    with app.app_context():
        conf = OrderConfirmation.query.get(confirmation["confirmation_id"])
        ctx = Collector.collect_order_confirmation_variables(
            conf, Customer.query.get(seed["customer_id"]),
            Order.query.get(confirmation["order_id"]))

        assert ctx['subtotal'] == '18,000,000'
        assert ctx['vat_amount'] == '1,440,000'
        assert ctx['total_amount'] == '19,440,000'
        assert len(ctx['items']) == 1


def test_citation_survives_the_agreement_being_renumbered(app, confirmation, seed):
    """The snapshot is the point: a reprint shows what was cited at issue."""
    from app.config import db
    from app.models import Customer, Order
    from app.models.models import MasterAgreement, OrderConfirmation

    with app.app_context():
        conf = OrderConfirmation.query.get(confirmation["confirmation_id"])
        ma = MasterAgreement.query.get(conf.master_agreement_id)
        ma.agreement_number = "HDNT-RENAMED"
        db.session.commit()

        ctx = Collector.collect_order_confirmation_variables(
            OrderConfirmation.query.get(confirmation["confirmation_id"]),
            Customer.query.get(seed["customer_id"]),
            Order.query.get(confirmation["order_id"]))

        assert ctx['cited_agreement_number'] == 'HDNT-DOC-1', (
            "the printed citation must be the snapshot, not the live value"
        )
