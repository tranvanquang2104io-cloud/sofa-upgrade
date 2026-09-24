"""The permission map must cover every route, and refuse the ones it does not.

The old resolver inferred an endpoint's area by matching substrings of its
name, and returned None when nothing matched. None meant "not gated", so a
route named unlike its area was open to every logged-in user with no way to
see it: the user form's tick boxes look complete whatever the map does.

`save_plan_norm` was exactly that — it contains no area's word, so it matched
nothing. It sits on the production plan screen beside `add_plan_material` and
`issue_plan_materials`, both of which WERE gated, so nothing looked odd.

Two properties replace the inference:

**Complete** — every live dashboard endpoint is in the map. A new route fails
this test until somebody writes down where it belongs, and the failure is the
question being asked.

**Closed** — an endpoint that is not in the map is refused, not admitted. This
is the half that matters: a complete map today says nothing about the route
somebody adds next month, and the safe direction for a forgotten route is
unreachable rather than open.

Also pinned here: the rows that are ungated because an admin decorator gates
them instead. That claim was previously made by a substring test of its own
(`if any(k in name for k in ('store', 'user', 'setting', ...))`) — the same
fragile mechanism one level down, where a future `restore_order` would have
matched 'store' and silently lost its gate.
"""
import pytest

from app.utils.permission_map import (
    ADMIN_SCREENS, ENDPOINT_FEATURE, UnmappedEndpoint, feature_for_endpoint,
)


def _live_endpoints(app):
    return {rule.endpoint.split('.', 1)[1]
            for rule in app.url_map.iter_rules()
            if rule.endpoint.startswith('dashboard.')}


def test_every_route_is_in_the_map(app):
    missing = sorted(_live_endpoints(app) - set(ENDPOINT_FEATURE))
    assert missing == [], (
        'these routes are in no permission area, so nobody has said who may '
        f'reach them: {missing}. Add them to app/utils/permission_map.py.')


def test_the_map_has_no_routes_that_no_longer_exist(app):
    """A stale row is a rule nobody can trip over — and a lie about coverage."""
    stale = sorted(set(ENDPOINT_FEATURE) - _live_endpoints(app))
    assert stale == [], (
        f'these entries name routes that do not exist: {stale}')


def test_an_unmapped_endpoint_is_refused_not_admitted():
    """The safe direction for a route nobody assigned is closed."""
    with pytest.raises(UnmappedEndpoint):
        feature_for_endpoint('dashboard.a_route_nobody_wrote_down')


def test_a_non_dashboard_endpoint_is_not_our_business():
    assert feature_for_endpoint('auth.login') is None
    assert feature_for_endpoint(None) is None


def test_every_admin_screen_really_carries_a_role_decorator(app):
    """`None` for an admin screen is a claim; this checks it.

    Those rows are ungated HERE because a role decorator gates them THERE. If
    one loses its decorator, the map's None becomes simply "open" and nothing
    else would notice.
    """
    view_functions = app.view_functions
    ungated_without_a_decorator = []
    for name in sorted(ADMIN_SCREENS):
        view = view_functions.get('dashboard.' + name)
        if view is None:
            continue
        # The decorators set this attribute on the wrapped view; see
        # app/utils/auth_utils.py.
        if not getattr(view, '_role_required', None):
            ungated_without_a_decorator.append(name)
    assert ungated_without_a_decorator == [], (
        'these screens are behind no permission area AND no role decorator, '
        f'so any logged-in user reaches them: {ungated_without_a_decorator}')


def test_issuing_material_stays_with_stock_and_editing_the_list_does_not():
    """§8.7, settled: the action decides the area, not the name.

    All four of these live on the production plan screen and three contain the
    word "material", which is why they were gated by the stock permission.
    Issuing genuinely deducts stock; adding a fabric line to a job does not.
    """
    assert feature_for_endpoint('dashboard.issue_plan_materials') == 'inventory'
    assert feature_for_endpoint('dashboard.add_plan_material') == 'orders'
    assert feature_for_endpoint('dashboard.delete_plan_material') == 'orders'
    assert feature_for_endpoint('dashboard.save_plan_norm') == 'orders'
