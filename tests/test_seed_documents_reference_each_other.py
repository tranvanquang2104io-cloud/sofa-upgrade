"""Seeded documents must actually reference what their text says they do.

The owner, §8.6: "data bên trong rất nhiều chứng từ chưa thực sự tham chiếu
hoặc hiển thị chính xác (hoặc do data seed chưa nhất quán)."

The GR-and-invoice half of that report turned out to be already fixed — both
screens have a way in and both detail templates render their parent. This is
the other half, and it was real.

**A payment that pays nothing.** The demo seeds a confirmed supplier payment
of 20.000.000 whose note reads "Trả một phần hóa đơn 0001234", and creates no
`SupplierPaymentAllocation`. The allocation table is not decoration — the
model's own docstring says "is this invoice paid?" is otherwise unanswerable.
So invoice 0001234 shows fully outstanding while the money has left the
company, the payment shows 20.000.000 unallocated, and the cash-VAT warning on
`payables/view.html` — which reaches the payment only through an allocation —
can never render on the demo at all. A person evaluating the product sees a
payables screen whose figures contradict its own notes.

**A method that is not one of the two methods.** The same payment is seeded
with `method='Chuyển khoản'`, free text, while the model defines
`METHOD_TRANSFER = 'bank_transfer'` and hangs `is_cash` off the constant.
Nothing breaks for a transfer, because wrong-and-not-cash still reads as not
cash. It breaks silently for the opposite: seed 'Tiền mặt' and `is_cash` stays
False, so the input-VAT warning the model exists to raise never appears on the
one payment that needs it. A value outside the enumeration is a defect even
when today's reading of it happens to be right.
"""
import pytest


@pytest.fixture(scope='module')
def demo(tmp_path_factory):
    """Run the real demo seed once, and look at what it produced."""
    import os

    os.environ['DATABASE_URL'] = 'sqlite:///' + str(
        tmp_path_factory.mktemp('seed') / 'demo.db').replace('\\', '/')

    from app import create_app
    from app.config import db

    application = create_app()
    with application.app_context():
        db.create_all()
        from scripts.seed_demo import seed
        seed()
    return application


def test_the_seeded_supplier_payment_settles_the_invoice_it_names(demo):
    from app.models.models import SupplierPayment

    with demo.app_context():
        payment = SupplierPayment.query.filter_by(
            payment_number='CHI-2609-0001').one()
        assert payment.allocations, (
            'the payment says it pays invoice 0001234 and is linked to no '
            'invoice at all, so that invoice reads as unpaid')
        assert payment.unallocated_amount == 0, (
            f'{payment.unallocated_amount} of the payment settles nothing')


def test_the_invoice_it_pays_is_no_longer_fully_outstanding(demo):
    from app.models.models import SupplierInvoice

    with demo.app_context():
        invoice = SupplierInvoice.query.filter_by(
            invoice_number='0001234').one()
        assert invoice.amount_outstanding < invoice.total_amount, (
            'money left the company and the payable did not move')
        assert not invoice.is_paid, (
            'the demo means to show a PART-paid invoice; a settled one shows '
            'nothing about instalments')


def test_every_seeded_payment_uses_a_method_the_model_defines(demo):
    """Free text here disables the cash flag without failing anything."""
    from app.models.models import SupplierPayment

    allowed = {SupplierPayment.METHOD_CASH, SupplierPayment.METHOD_TRANSFER}
    with demo.app_context():
        for payment in SupplierPayment.query.all():
            assert payment.method in allowed, (
                f'{payment.payment_number} has method {payment.method!r}, '
                f'which is not one of {sorted(allowed)}; is_cash is therefore '
                'False whatever was meant')


def test_a_rebuild_leaves_no_orphan_allocations(demo):
    """`wipe()` must reach rows that carry no company_id.

    An allocation is addressed only by its two foreign keys, so the
    company-scoped delete that clears invoices and payments cannot see it, and
    a rebuild would leave rows pointing at deleted parents.

    The rebuild is `wipe()` then `seed()` — the path `--reset` takes. Calling
    `seed()` twice is not that path: it always builds a fresh company and
    `main()` refuses the second run unless asked to reset. The first version of
    this test called it twice and failed on a unique company_code, which said
    nothing about allocations.
    """
    from app.models import Company
    from app.models.models import SupplierPayment, SupplierPaymentAllocation
    from scripts.seed_demo import COMPANY_CODE, seed, wipe

    with demo.app_context():
        wipe(Company.query.filter_by(company_code=COMPANY_CODE).one().id)
        assert SupplierPaymentAllocation.query.count() == 0, (
            'allocations survived the wipe that removed their payments')

        seed()
        payment_ids = {p.id for p in SupplierPayment.query.all()}
        for allocation in SupplierPaymentAllocation.query.all():
            assert allocation.payment_id in payment_ids
