"""The screen must say which stock the figures are about — and it changed.

This file used to pin the OPPOSITE of what it pins now, and the change is the
point.

Purchase suggestions compared requirement against `Material.total_stock`, the
sum over every branch, while issuing drew from one branch. A workshop needing
20m and holding none was told to buy nothing because 50m sat at the showroom,
and the shortage surfaced on the day of cutting. The screen carried a warning
saying so — "một chi nhánh có thể thấy 'đủ tồn' trong khi vật tư đang nằm ở
chi nhánh khác" — which was honest about a defect rather than a fix for it.

The arithmetic now aggregates per production site. The warning is therefore
obsolete: leaving it would teach the user something that is no longer true,
which is worse than never having said it.

What is still true, and still worth saying on the screen: the Tồn column shows
the company-wide total. A buyer wants to know the fabric exists somewhere in
the business even when this workshop cannot reach it — but the number to buy
no longer comes from it.
"""
import io
import pathlib

SCREEN = (pathlib.Path(__file__).resolve().parents[1] / 'app' / 'templates'
          / 'materials' / 'purchase_suggestions.html')


def test_the_suggestion_is_computed_per_production_site():
    import inspect

    from app.services import services

    source = inspect.getsource(
        services.ProductionPlanService.purchase_suggestions)
    assert 'production_site_of' in source, (
        'suggestions are back to counting company-wide stock, so a branch can '
        'again be told it has fabric that is somewhere else')


def test_the_screen_no_longer_warns_about_a_defect_that_is_fixed():
    text = io.open(SCREEN, encoding='utf-8').read()
    assert 'có thể thấy “đủ tồn”' not in text, (
        'the screen still warns that a branch may look stocked when the '
        'material is elsewhere; that was true of the old arithmetic')


def test_the_screen_still_says_what_the_stock_column_means():
    """The column is company-wide and the suggestion is not — say both."""
    text = io.open(SCREEN, encoding='utf-8').read()
    assert 'từng nơi sản\n  xuất' in text or 'từng nơi sản xuất' in text, (
        'nothing tells the user the suggestion is per production site')
    assert 'toàn công ty' in text, (
        'the Tồn column is a company-wide total and the screen no longer says '
        'so')
