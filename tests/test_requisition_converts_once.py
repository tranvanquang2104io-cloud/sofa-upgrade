"""Pressing "Tạo PO từ đề nghị" twice must not order everything twice.

`can_convert()` returned True for a requisition that had ALREADY been
converted, with a docstring promising it would create "phần còn lại" — the
remainder. Nothing implements that: `convert_to_pos` walks every line of the
requisition each time it is called, and no field records what was converted
before. So the second press produces a full second set of purchase orders for
the same requirement, and if both are sent, the company buys the fabric twice
and owes for it twice.

The remainder story cannot be implemented without somewhere to record it — a
`quantity_converted` per line, which the model does not have. Inventing that
here would be adding a feature to fix a defect. So a requisition converts once,
and `can_convert()` now says what is actually true.

Partial conversion stays possible to build later; it is recorded in the ledger
rather than half-built now.
"""
import pytest

from app.models.models import PurchaseRequisition


@pytest.fixture()
def approved_requisition(app, seed):
    from app.config import db
    from app.models.models import (
        Material, PurchaseRequisition, PurchaseRequisitionLine, Supplier,
    )

    with app.app_context():
        supplier = Supplier(company_id=seed['company_id'],
                            supplier_code='NCC-PR', name='Vải Thiên Hà',
                            is_active=True)
        db.session.add(supplier)
        db.session.flush()
        material = Material(company_id=seed['company_id'],
                            material_code='VAI-PR', name='Vải nhung',
                            supplier_id=supplier.id, is_active=True)
        db.session.add(material)
        db.session.flush()

        requisition = PurchaseRequisition(
            company_id=seed['company_id'], pr_number='PR-ONCE',
            status=PurchaseRequisition.STATUS_APPROVED)
        db.session.add(requisition)
        db.session.flush()
        db.session.add(PurchaseRequisitionLine(
            pr_id=requisition.id, material_id=material.id,
            quantity=30, unit='m'))
        db.session.commit()
        return {**seed, 'pr_id': str(requisition.id)}


def test_an_approved_requisition_converts():
    """The ordinary path must keep working."""
    requisition = PurchaseRequisition(
        status=PurchaseRequisition.STATUS_APPROVED)
    assert requisition.can_convert()


def test_a_converted_requisition_does_not_convert_again():
    requisition = PurchaseRequisition(
        status=PurchaseRequisition.STATUS_CONVERTED)
    assert not requisition.can_convert(), (
        'a second press would order the whole requirement a second time')


def test_converting_twice_creates_one_set_of_orders(app,
                                                    approved_requisition):
    from app.models.models import PurchaseOrder, PurchaseRequisition
    from app.services.requisition_service import RequisitionService

    with app.app_context():
        requisition = PurchaseRequisition.query.get(
            approved_requisition['pr_id'])
        RequisitionService().convert_to_pos(requisition)

        requisition = PurchaseRequisition.query.get(
            approved_requisition['pr_id'])
        with pytest.raises(ValueError):
            RequisitionService().convert_to_pos(requisition)

        orders = PurchaseOrder.query.filter_by(
            company_id=approved_requisition['company_id']).all()

    assert len(orders) == 1, (
        f'{len(orders)} purchase orders exist for one requisition')


def test_the_quantity_ordered_is_the_quantity_requested(app,
                                                        approved_requisition):
    """Not doubled, and not halved."""
    from app.models.models import PurchaseOrderLine, PurchaseRequisition
    from app.services.requisition_service import RequisitionService

    with app.app_context():
        requisition = PurchaseRequisition.query.get(
            approved_requisition['pr_id'])
        RequisitionService().convert_to_pos(requisition)

        total = sum(float(line.quantity_ordered)
                    for line in PurchaseOrderLine.query.all())

    assert total == 30
