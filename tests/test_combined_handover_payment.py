"""Item 4 (combined handover + final payment) and item 5 (payment proof upload)."""
from datetime import date
from decimal import Decimal


def _setup_order_ready_for_handover(app, seed):
    """Order with a signed contract and advance already paid (skip-advance path)."""
    from app.config import db
    from app.models.models import Order, Contract, LifecycleStatus
    cid, sid = seed['company_id'], seed['store_id']
    with app.app_context():
        o = Order(company_id=cid, store_id=sid, customer_id=seed['customer_id'],
                  order_code='CMB-O1', title='Bộ sofa')
        db.session.add(o); db.session.flush()
        db.session.add(Contract(order_id=o.id, company_id=cid, contract_number='CMB-C1',
                                contract_date=date(2026, 8, 1), contract_value=Decimal('10000000')))
        lc = LifecycleStatus(order_id=o.id, contract_signed=True,
                             advance_paid=True, advance_skipped=True)
        db.session.add(lc)
        db.session.commit()
        return str(o.id)


def test_combined_handover_creates_final_payment(app, seed):
    from app.config import db
    from app.models.models import PaymentReport
    from app.services.services import HandoverRecordService
    from app.routes.dashboard_routes import _create_final_payment_from_handover
    cid = seed['company_id']
    order_id = _setup_order_ready_for_handover(app, seed)

    with app.app_context():
        ho = HandoverRecordService().create_handover_record(
            order_id=order_id, report_number='CMB-BG1', report_date=date(2026, 8, 2),
            handover_date=date(2026, 8, 2),
            items=[{'name': 'Ghế sofa', 'unit': 'Bộ', 'accepted_qty': 1,
                    'unit_price': 10000000, 'total': 10000000}],
            subtotal=10000000, vat_rate=0, vat_amount=0, total_amount=10000000)
        db.session.commit()
        HandoverRecordService().confirm_handover(ho.id, order_id)
        _create_final_payment_from_handover(order_id, cid, ho)

    with app.app_context():
        finals = PaymentReport.query.filter_by(order_id=order_id, payment_type='final').all()
        assert len(finals) == 1
        p = finals[0]
        assert float(p.amount) == 10000000.0
        assert float(p.advance_amount) == 0.0          # no confirmed advance (skipped)
        assert float(p.remaining_amount) == 10000000.0
        assert not p.is_confirmed                       # left as draft


def test_payment_proof_path_persists(app, seed):
    """The new proof_path column stores and reads back the uploaded proof reference."""
    from app.config import db
    from app.models.models import PaymentReport
    order_id = _setup_order_ready_for_handover(app, seed)
    with app.app_context():
        p = PaymentReport(order_id=order_id, report_number='CMB-TT1', payment_type='final',
                          report_date=date(2026, 8, 3), payment_date=date(2026, 8, 3),
                          amount=Decimal('5000000'), proof_path='items/abc.pdf')
        db.session.add(p); db.session.commit()
        pid = str(p.id)
    with app.app_context():
        assert PaymentReport.query.get(pid).proof_path == 'items/abc.pdf'
