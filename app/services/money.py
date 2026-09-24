"""Single source of truth for document money arithmetic.

Before this module the formula ``subtotal + vat + shipping + another_fee`` was
re-derived in ~7 route handlers (quotation/contract/handover/payment, create
and edit), each one hardcoding ``float(request.form.get('vat_rate') or 8)``.
That had three consequences:

* the literal ``8`` shadowed ``Company.vat_rate``, a per-company setting that
  already existed in the schema but was never actually read;
* rounding was done with floats, so totals could drift a cent from the stored
  line items;
* any caller that did *not* go through a route (services, scripts, imports)
  could write a total inconsistent with ``items``.

Business rules encoded here (see UPDATE_PLAN.md §1, confirmed with the owner):
VAT applies to the line-item subtotal ONLY. Shipping and "another" fees are
added after VAT and are never taxed.

All arithmetic is done with ``Decimal``. Values are returned as floats because
that is what the existing JSON/columns store, but the rounding happens before
the conversion so the stored numbers agree with the documents produced.
"""
from decimal import Decimal, ROUND_HALF_UP

# Used only when neither the caller nor the company specifies a rate. Kept as
# the historical default so existing behaviour is preserved.
FALLBACK_VAT_RATE = Decimal('8')

_CENTS = Decimal('0.01')


def to_decimal(value, default='0'):
    """Coerce form input / ORM values to Decimal without float drift.

    Blank strings and None fall back to ``default``; anything unparseable
    raises ValueError so a bad amount surfaces instead of silently becoming 0.
    """
    if value is None or value == '':
        return Decimal(str(default))
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


# The product's rounding rule, named so other modules can follow it rather
# than re-deciding. A bare `quantize` takes Decimal's default, which is
# ROUND_HALF_EVEN and rounds the other way on exact halves.
ROUND_HALF_UP_RULE = ROUND_HALF_UP


def _round(value):
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


def subtotal_from_items(items):
    """Re-derive the subtotal from stored line items.

    Used to verify that a document's ``subtotal`` column still agrees with its
    ``items`` JSON (they could previously diverge — e.g. a contract copies the
    quotation's items but took ``contract_value`` from the caller).
    """
    total = Decimal('0')
    for item in items or []:
        line = item.get('total')
        if line is None:
            line = (to_decimal(item.get('quantity'))
                    * to_decimal(item.get('unit_price')))
        total += to_decimal(line)
    return _round(total)


def resolve_vat_rate(submitted=None, company=None):
    """Pick the VAT rate: explicit form value > company setting > fallback.

    This is what makes ``Company.vat_rate`` actually take effect; previously
    the routes jumped straight to the hardcoded 8.
    """
    if submitted not in (None, ''):
        return to_decimal(submitted)
    if company is not None and getattr(company, 'vat_rate', None) is not None:
        return to_decimal(company.vat_rate)
    return FALLBACK_VAT_RATE


def compute_totals(subtotal, vat_rate=None, shipping_fee=0, another_fee=0,
                   company=None):
    """Compute VAT and the grand total for a document.

    Returns a dict of floats: ``subtotal``, ``vat_rate``, ``vat_amount``,
    ``shipping_fee``, ``another_fee``, ``total_amount``.

    VAT is charged on the subtotal only; the two fees are added afterwards and
    are not taxed.
    """
    sub = _round(to_decimal(subtotal))
    rate = resolve_vat_rate(vat_rate, company)
    shipping = _round(to_decimal(shipping_fee))
    another = _round(to_decimal(another_fee))

    if sub < 0 or shipping < 0 or another < 0:
        raise ValueError('Amounts cannot be negative')
    if rate < 0:
        raise ValueError('VAT rate cannot be negative')

    vat_amount = _round(sub * rate / Decimal('100'))
    total = _round(sub + vat_amount + shipping + another)

    return {
        'subtotal': float(sub),
        'vat_rate': float(rate),
        'vat_amount': float(vat_amount),
        'shipping_fee': float(shipping),
        'another_fee': float(another),
        'total_amount': float(total),
    }


def totals_from_form(form, company=None, subtotal=None, items=None):
    """Compute a document's totals straight from a submitted form.

    ``subtotal`` normally comes from ``parse_line_items``; when it is omitted
    it is re-derived from ``items`` so the total can never disagree with the
    lines it is built from.
    """
    if subtotal is None:
        subtotal = subtotal_from_items(items)
    return compute_totals(
        subtotal=subtotal,
        vat_rate=form.get('vat_rate'),
        shipping_fee=form.get('shipping_fee'),
        another_fee=form.get('another_fee'),
        company=company,
    )
