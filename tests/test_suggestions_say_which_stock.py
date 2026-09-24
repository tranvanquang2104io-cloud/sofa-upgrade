"""The suggestion screen must say whose stock it is counting.

Purchase suggestions subtract `Material.total_stock` — every location the
company holds. Issuing subtracts from `order.store_id` — the branch doing the
work. Both are defensible on their own: you buy for the company, you issue from
a shelf. Together, and unlabelled, they mislead.

With two branches the column headed simply "Tồn" reads as "what I have". A
supervisor at Quận 7 sees 50 metres, buys nothing, and is refused at issue time
because the 50 metres are in Thủ Đức. The system knew both numbers and showed
the one that was not theirs.

The calculation is NOT changed here. Whether purchasing should be per-branch
depends on whether branches share stock and whether a transfer exists — neither
is something to infer from a column header. What changes is that the screen
says which figure it is showing, so the number can be trusted for what it is.
The question itself is recorded in the ledger.
"""
import pytest


def test_the_screen_says_the_stock_figure_is_company_wide(client, login, seed):
    login('admin')
    body = client.get('/materials/purchase-suggestions').get_data(as_text=True)
    assert 'toàn công ty' in body, (
        'the stock column does not say which stock it counts, so a branch '
        'reads it as their own')


def test_the_two_figures_still_come_from_different_places(app, seed):
    """Pinning the thing that makes the label necessary.

    If these ever converge, the label becomes wrong rather than merely
    unnecessary — so the difference is asserted, not assumed.
    """
    import inspect

    from app.services import services

    suggestions = inspect.getsource(
        services.ProductionPlanService.purchase_suggestions)
    issuing = inspect.getsource(services.ProductionPlanService._stock_for)

    assert 'total_stock' in suggestions, (
        'suggestions no longer use company-wide stock; the label needs revising'
    )
    assert 'store_id' in issuing, (
        'issuing no longer resolves stock per store; the label needs revising'
    )
