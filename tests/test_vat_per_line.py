"""A line may carry its own VAT rate, and a document that uses none must not move.

The owner asked for VAT per line item, because a real invoice can carry two
rates: sofa frames at 8% beside a steel bed frame at 10% (metal products are
excluded from the 2% reduction), or goods delivered either side of
31/12/2026, when Nghị quyết 204/2025 expires and the rate returns to 10%.
Today `vat_rate` sits on the document header — one rate for everything — so
that invoice cannot be expressed at all.

It is built as a **cascade, not a switch**: a line's rate is its own if it has
one, else the document's, else the company's. Two consequences, and they are
the reason for the shape:

* Nobody has to answer "which mode are my 200 existing orders in?" An old line
  carries no rate of its own, so it takes the document's — the same number as
  before. A switch would have had to answer that question; a cascade does not
  raise it.
* There is no second branch to test. A switch multiplies the paths through
  every screen that shows money; a cascade adds one direction.

The invariant below is the one that matters: when every line agrees, the
result must be **identical** to what the old single-rate path produced,
down to the đồng. If that ever fails, 200 printed documents disagree with what
the system now says they say.

The fee rule is unchanged and deliberate: VAT applies to the line subtotal
only; shipping and the second fee are added after VAT and are never taxed.
With per-line VAT the tax must therefore be summed from the lines BEFORE the
fees are added, not computed on a blended total — that ordering is what keeps
the invariant true.
"""
import decimal

import pytest

from app.services.money import compute_totals


def _items(*rows):
    """(quantity, unit_price) or (quantity, unit_price, vat_rate)."""
    out = []
    for row in rows:
        item = {'quantity': row[0], 'unit_price': row[1],
                'total': row[0] * row[1]}
        if len(row) > 2:
            item['vat_rate'] = row[2]
        out.append(item)
    return out


# --------------------------------------------------------------------------
# The invariant: nothing moves for a document that does not use the feature.
# --------------------------------------------------------------------------

@pytest.mark.parametrize('rate', [0, 5, 8, 10])
@pytest.mark.parametrize('shipping, another', [(0, 0), (700_000, 250_000)])
def test_lines_without_a_rate_give_exactly_the_old_answer(rate, shipping,
                                                          another):
    items = _items((1, 40_000_000), (2, 2_500_000))
    old = compute_totals(subtotal=45_000_000, vat_rate=rate,
                         shipping_fee=shipping, another_fee=another)
    new = compute_totals(subtotal=45_000_000, vat_rate=rate,
                         shipping_fee=shipping, another_fee=another,
                         items=items)
    assert new == old


@pytest.mark.parametrize('rate', [0, 8, 10])
def test_lines_that_all_state_the_same_rate_agree_with_the_header(rate):
    """Stating the rate explicitly on every line must change nothing."""
    items = _items((1, 40_000_000, rate), (2, 2_500_000, rate))
    stated = compute_totals(subtotal=45_000_000, vat_rate=rate, items=items)
    header_only = compute_totals(subtotal=45_000_000, vat_rate=rate)
    assert stated == header_only


# --------------------------------------------------------------------------
# What the feature is for.
# --------------------------------------------------------------------------

def test_two_rates_on_one_document_are_taxed_separately():
    """A sofa at 8% beside a steel bed frame at 10%."""
    items = _items((1, 40_000_000, 8),      # 3.200.000
                   (1, 12_000_000, 10))     # 1.200.000
    totals = compute_totals(subtotal=52_000_000, vat_rate=8, items=items)

    assert totals['vat_amount'] == 4_400_000, (
        'both lines were taxed at one rate; the whole point is that they are '
        'not')
    assert totals['total_amount'] == 56_400_000


def test_a_line_without_a_rate_falls_back_to_the_document():
    items = _items((1, 40_000_000),          # takes the document's 8%
                   (1, 12_000_000, 10))
    totals = compute_totals(subtotal=52_000_000, vat_rate=8, items=items)
    assert totals['vat_amount'] == 4_400_000


def test_a_mixed_document_says_so_instead_of_printing_one_rate_as_the_rate():
    """The header rate is printed. It must not be read as "the rate" when two apply.

    The first version of this test made `vat_rate` None for a mixed document,
    on the grounds that no single number is correct. That is true of what the
    header MEANS, and wrong as a value: seven callers and the .docx templates
    read that key expecting a number, so None would have printed blank or
    raised. The header rate keeps its job — it is the rate a line takes when
    it states none — and a separate flag carries the fact that some line did.
    """
    items = _items((1, 40_000_000, 8), (1, 12_000_000, 10))
    mixed = compute_totals(subtotal=52_000_000, vat_rate=8, items=items)
    assert mixed['vat_rate'] == 8, 'the document rate is still a number'
    assert mixed['vat_is_mixed'] is True, (
        'nothing tells the screen that one rate does not describe this '
        'document')

    plain = compute_totals(subtotal=45_000_000, vat_rate=8)
    assert plain['vat_is_mixed'] is False


def test_fees_are_still_untaxed_when_lines_carry_their_own_rates():
    items = _items((1, 40_000_000, 8), (1, 12_000_000, 10))
    totals = compute_totals(subtotal=52_000_000, vat_rate=8, items=items,
                            shipping_fee=700_000, another_fee=300_000)
    assert totals['vat_amount'] == 4_400_000, 'a fee was taxed'
    assert totals['total_amount'] == 57_400_000


def test_each_line_rounds_the_way_this_module_already_rounds():
    """Per-line VAT must follow the same rule as the single-rate path.

    Which is: to the hào (two places), half up. The first version of this test
    asserted rounding to the đồng and failed — that is `_round_dong` in
    payables_service, the PURCHASE side, borrowed here by mistake. A test that
    imports a rule from the wrong module reports the code as wrong when it is
    obeying its own rule correctly.
    """
    items = _items((3, 8_333, 8))     # 24.999 × 8% = 1999.92
    per_line = compute_totals(subtotal=24_999, vat_rate=0, items=items)
    single = compute_totals(subtotal=24_999, vat_rate=8)
    assert per_line['vat_amount'] == single['vat_amount']
    assert decimal.Decimal(str(per_line['vat_amount'])) ==         decimal.Decimal('1999.92')


def test_a_negative_line_rate_is_refused_like_any_other():
    items = _items((1, 1_000_000, -5))
    with pytest.raises(ValueError):
        compute_totals(subtotal=1_000_000, vat_rate=8, items=items)


# --------------------------------------------------------------------------
# The wire. Unit tests on compute_totals prove the arithmetic; only this
# proves a rate typed on a screen reaches it.
# --------------------------------------------------------------------------

@pytest.fixture()
def order(app, seed):
    from app.config import db
    from app.models import Order

    with app.app_context():
        record = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                       customer_id=seed['customer_id'], order_code='DH-VAT',
                       title='Sofa góc L')
        db.session.add(record)
        db.session.commit()
        return {**seed, 'order_id': str(record.id)}


def test_a_rate_typed_on_a_line_reaches_the_stored_total(client, login, app,
                                                         order):
    """Sofa 40tr at 8% beside a steel frame 12tr at 10% = 4.400.000 VAT."""
    login('admin')
    response = client.post(
        f"/quotations/{order['order_id']}/create",
        data={
            'quotation_number': 'BG-VAT-01',
            'quotation_date': '2026-09-25',
            'vat_rate': '8',
            'item_name[]': ['Sofa góc L', 'Khung giường sắt'],
            'item_quantity[]': ['1', '1'],
            'item_price[]': ['40000000', '12000000'],
            'item_vat_rate[]': ['8', '10'],
        }, follow_redirects=True)
    assert response.status_code == 200

    from app.models.models import Quotation
    with app.app_context():
        quotation = Quotation.query.filter_by(
            quotation_number='BG-VAT-01').one()
        assert float(quotation.vat_amount) == 4_400_000, (
            'the 10% line was taxed at the document rate, so the rate typed '
            'on the line never reached the arithmetic')
        assert float(quotation.total_amount) == 56_400_000
        assert quotation.items[1]['vat_rate'] == 10, (
            'the rate was not stored on the line, so re-opening the quotation '
            'would lose it')


def test_a_form_that_sends_no_line_rates_is_unchanged(client, login, app,
                                                      order):
    """Every screen in the product sends exactly this shape today."""
    login('admin')
    client.post(
        f"/quotations/{order['order_id']}/create",
        data={
            'quotation_number': 'BG-VAT-02',
            'quotation_date': '2026-09-25',
            'vat_rate': '8',
            'item_name[]': ['Sofa góc L'],
            'item_quantity[]': ['1'],
            'item_price[]': ['40000000'],
        }, follow_redirects=True)

    from app.models.models import Quotation
    with app.app_context():
        quotation = Quotation.query.filter_by(
            quotation_number='BG-VAT-02').one()
        assert float(quotation.vat_amount) == 3_200_000
        assert 'vat_rate' not in quotation.items[0], (
            'a line nobody gave a rate now carries one, which would make '
            'every old document look like it uses the feature')
