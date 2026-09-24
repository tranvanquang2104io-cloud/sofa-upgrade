"""A rejected form must say why, and must not throw the work away.

Three symptoms of one defect, on the screen with the most typing in the
product.

**The Save button disables itself in silence.** Typing a number already in use
sets `submitBtn.disabled = true` and toggles a warning with `style.display`.
There is no `aria-live` and no `aria-describedby`, so a screen-reader user
hears nothing; a disabled button leaves the tab order, so a keyboard user
cannot even reach it to find out why. They press Save and nothing happens at
all.

**The warning is in English** on a Vietnamese screen: "This code is already in
use!", hard-coded, not even wrapped in `t()`.

**If the server does reject, the form comes back blank.** The route re-renders
`quotations/create.html` with only `order` and `company_vat_rate`, and no
template reads `request.form` — so every line item, price, VAT and shipping
charge the user typed is gone, and the only thing they are told is a flash at
the top of the page. WCAG 3.3.4, and simply cruel on a form that takes ten
minutes to fill.

The three are one defect because fixing any one alone makes another worse: stop
disabling the button and the blank-form path becomes the common one.
"""
import io
import pathlib
import re

import pytest

TEMPLATES = pathlib.Path(__file__).resolve().parents[1] / 'app' / 'templates'
CREATE = TEMPLATES / 'quotations' / 'create.html'

# All four document create screens carry the same duplicate-number checker,
# copied between them. Fixing one and leaving three is how the copies drifted
# apart in the first place.
CODE_SCREENS = [
    'quotations/create.html',
    'contracts/create.html',
    'handover/create.html',
    'payments/create.html',
]
CODE_FIELDS = {
    'quotations/create.html': 'quotation_number',
    'contracts/create.html': 'contract_number',
    'handover/create.html': 'report_number',
    'payments/create.html': 'report_number',
}


@pytest.fixture()
def order_with_a_used_number(app, seed):
    import datetime as dt

    from app.config import db
    from app.models import Order
    from app.models.models import Quotation

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-DUP',
                      title='Sofa góc L')
        db.session.add(order)
        db.session.flush()
        db.session.add(Quotation(
            company_id=seed['company_id'], order_id=order.id,
            quotation_number='BG-TAKEN', quotation_date=dt.date(2026, 9, 1),
            total_amount=1_000_000))
        db.session.commit()
        return {**seed, 'order_id': str(order.id)}


@pytest.mark.parametrize('screen', CODE_SCREENS)
def test_the_duplicate_warning_is_announced(screen):
    """A warning shown only by toggling display reaches nobody using a reader."""
    text = io.open(TEMPLATES / screen, encoding='utf-8').read()
    warning = re.search(r'<div id="code-warning"[^>]*>', text)
    assert warning, 'the duplicate-code warning is gone'
    assert 'aria-live' in warning.group(0), (
        'the warning appears silently for a screen-reader user')


@pytest.mark.parametrize('screen', CODE_SCREENS)
def test_the_field_points_at_its_warning(screen):
    text = io.open(TEMPLATES / screen, encoding='utf-8').read()
    name = CODE_FIELDS[screen]
    field = re.search(r'<input[^>]*id="%s"[^>]*>' % name, text)
    assert field, f'the {name} field is gone from {screen}'
    assert 'aria-describedby="code-warning"' in field.group(0), (
        f'nothing connects the field to the warning about it in {screen}')


@pytest.mark.parametrize('screen', CODE_SCREENS)
def test_the_warning_is_in_vietnamese(screen):
    text = io.open(TEMPLATES / screen, encoding='utf-8').read()
    assert 'This code is already in use!' not in text, (
        'a Vietnamese user is warned in English'
    )


@pytest.mark.parametrize('screen', CODE_SCREENS)
def test_the_save_button_is_not_silently_disabled(screen):
    """Refusing with a reason beats refusing with nothing."""
    text = io.open(TEMPLATES / screen, encoding='utf-8').read()
    assert 'submitBtn.disabled = !!d.exists' not in text, (
        'the button still disables itself, so pressing Save does nothing and '
        'says nothing')


def test_a_rejected_quotation_keeps_what_was_typed(client, login,
                                                   order_with_a_used_number):
    """The work is ten minutes of typing; losing it is the real harm."""
    login('admin')
    response = client.post(
        f"/quotations/{order_with_a_used_number['order_id']}/create",
        data={
            'quotation_number': 'BG-TAKEN',       # already used
            'quotation_date': '2026-09-20',
            'notes': 'Giao trước Tết, bọc vải nhung xanh rêu',
            'item_name[]': ['Sofa góc L', 'Đôn vuông'],
            'item_quantity[]': ['1', '2'],
            'item_price[]': ['40000000', '2500000'],
            'shipping_fee': '700000',
        }, follow_redirects=True)

    body = response.get_data(as_text=True)
    assert 'Giao trước Tết, bọc vải nhung xanh rêu' in body, (
        'the notes the user typed were thrown away')
    assert 'Sofa góc L' in body, 'the line items were thrown away'
    assert '700000' in body.replace(',', '').replace('.', ''), (
        'the delivery fee was thrown away')


def test_a_rejected_payment_keeps_the_work_items(client, login, app, seed):
    """The same defect, on the screen where it costs the most.

    Fixing this for the quotation left contract, payment and handover as they
    were — each keeps only its document number on a refusal and throws away
    every line the user typed. Found while converging the line-item row: adding
    the payment screen to that test's list failed, and the failure was right.

    Contract and handover still have it; recorded in REFACTOR-2026Q3.md rather
    than fixed here, because each rebuilds a different set of fields and doing
    them blind is how a rebuild drops one.
    """
    import datetime as dt

    from app.config import db
    from app.models import Order
    from app.models.models import PaymentReport

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-PAYDUP',
                      title='Sofa góc L')
        db.session.add(order)
        db.session.flush()
        db.session.add(PaymentReport(
            company_id=seed['company_id'], order_id=order.id,
            report_number='TT-TAKEN', report_date=dt.date(2026, 9, 1),
            payment_date=dt.date(2026, 9, 1),
            payment_type='advance', amount=1_000_000))
        db.session.commit()
        order_id = str(order.id)

    login('admin')
    response = client.post(
        f'/payment/{order_id}/create',
        data={
            'report_number': 'TT-TAKEN',          # already used
            'report_date': '2026-09-25',
            'payment_type': 'advance',
            'item_name[]': ['Thi công khung ghế', 'Bọc da'],
            'item_quantity[]': ['1', '2'],
            'item_price[]': ['12000000', '3500000'],
        }, follow_redirects=True)

    body = response.get_data(as_text=True)
    assert 'Thi công khung ghế' in body, (
        'the work items the user typed were thrown away')
    assert '12000000' in body.replace(',', '').replace('.', ''), (
        'the amounts were thrown away')
