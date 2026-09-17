"""Arithmetic contract for app/services/money.py.

These pin the rules that were previously re-implemented in ~7 route handlers,
so the behaviour cannot drift when those call sites are consolidated.
"""
import pytest

from app.services.money import (
    FALLBACK_VAT_RATE,
    compute_totals,
    resolve_vat_rate,
    subtotal_from_items,
)


class _Company:
    def __init__(self, vat_rate):
        self.vat_rate = vat_rate


def test_vat_applies_to_subtotal_only_not_to_fees():
    """The core business rule: shipping and other fees are never taxed."""
    r = compute_totals(subtotal=10_000_000, vat_rate=8,
                       shipping_fee=500_000, another_fee=200_000)

    assert r['vat_amount'] == 800_000.0, "VAT must be 8% of the subtotal alone"
    assert r['total_amount'] == 11_500_000.0
    # If VAT had been charged on the fees too the total would be 11_556_000.


def test_total_is_subtotal_plus_vat_plus_both_fees():
    r = compute_totals(subtotal=1_000, vat_rate=10, shipping_fee=1, another_fee=2)
    assert r['total_amount'] == pytest.approx(1_000 + 100 + 1 + 2)


def test_zero_vat_rate_is_honoured_not_replaced_by_default():
    """0 is a real rate (VAT-exempt), it must not fall through to the default."""
    r = compute_totals(subtotal=5_000_000, vat_rate=0)
    assert r['vat_amount'] == 0.0
    assert r['total_amount'] == 5_000_000.0


def test_company_vat_rate_is_used_when_form_omits_it():
    """Company.vat_rate existed in the schema but the routes ignored it."""
    r = compute_totals(subtotal=1_000_000, vat_rate=None,
                       company=_Company(vat_rate=5))
    assert r['vat_rate'] == 5.0
    assert r['vat_amount'] == 50_000.0


def test_submitted_rate_overrides_company_rate():
    r = compute_totals(subtotal=1_000_000, vat_rate=10,
                       company=_Company(vat_rate=5))
    assert r['vat_rate'] == 10.0


def test_falls_back_to_default_when_no_rate_anywhere():
    assert resolve_vat_rate(None, None) == FALLBACK_VAT_RATE
    r = compute_totals(subtotal=1_000_000)
    assert r['vat_amount'] == 80_000.0


def test_blank_form_values_are_treated_as_zero_not_errors():
    """Empty form inputs are normal; they must not blow up."""
    r = compute_totals(subtotal=100, vat_rate='', shipping_fee='', another_fee=None)
    assert r['vat_rate'] == float(FALLBACK_VAT_RATE)
    assert r['shipping_fee'] == 0.0
    assert r['another_fee'] == 0.0


def test_negative_amounts_are_rejected():
    with pytest.raises(ValueError):
        compute_totals(subtotal=-1)
    with pytest.raises(ValueError):
        compute_totals(subtotal=100, shipping_fee=-5)
    with pytest.raises(ValueError):
        compute_totals(subtotal=100, vat_rate=-1)


def test_decimal_arithmetic_does_not_drift_on_repeated_thirds():
    """Float accumulation used to be able to leave a cent behind."""
    items = [{'quantity': 3, 'unit_price': 0.1}] * 3
    assert float(subtotal_from_items(items)) == pytest.approx(0.9)


def test_subtotal_from_items_recomputes_when_line_total_missing():
    items = [
        {'quantity': 2, 'unit_price': 1_500_000},          # no 'total' key
        {'quantity': 1, 'unit_price': 500_000, 'total': 500_000},
    ]
    assert float(subtotal_from_items(items)) == 3_500_000.0


def test_subtotal_from_items_handles_empty_and_none():
    assert float(subtotal_from_items([])) == 0.0
    assert float(subtotal_from_items(None)) == 0.0


def test_rounding_is_half_up_as_accounting_expects():
    """VND/accounting rounds .005 up; Python's round() would round to even."""
    r = compute_totals(subtotal='0.05', vat_rate=10)
    # 0.05 * 10% = 0.005 -> 0.01, not 0.00
    assert r['vat_amount'] == 0.01
