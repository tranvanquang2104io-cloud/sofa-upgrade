"""Where the app sends you after an action, when it does not know where you were.

Ten handlers ended with `redirect(request.referrer)`. Two problems, both only
visible to a user who arrived without a Referer header — which is every user who
opens a link directly, uses a bookmark, or whose browser or privacy setting
strips it.

1. `redirect(None)` does not fail loudly. It emits `Location: None`, so the
   browser navigates to a relative path literally named "None" and lands on a
   404. For a non-technical user that is a dead end with no explanation, right
   after an action they were told had failed.

2. The Referer header is attacker-controllable: a page on another site can send
   a user into the app, and the app then bounces them back out to that site. The
   codebase already refuses that for `next` parameters via
   `_is_safe_redirect_url`, but that helper requires a relative path and a
   referrer is always absolute, so it could not simply be reused here.
"""
import pytest

from app.routes.dashboard_routes import _safe_back_url


@pytest.fixture()
def a_document(app, seed):
    from app.config import db
    from app.models import Document, Order

    with app.app_context():
        o = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                  customer_id=seed['customer_id'], order_code='DH-BACK',
                  title='Sofa')
        db.session.add(o)
        db.session.flush()
        d = Document(company_id=seed['company_id'], order_id=o.id,
                     document_name='BaoGia', document_type='quotation',
                     document_format='pdf', file_path='/nonexistent/file.pdf')
        db.session.add(d)
        db.session.commit()
        return {'document_id': str(d.id), **seed}


# --- the helper ----------------------------------------------------------

@pytest.mark.parametrize("referrer", [
    None,                                   # opened directly / bookmarked
    '',                                     # header present but empty
    'https://evil.com/steal',               # another site entirely
    '//evil.com/steal',                     # protocol-relative
    'javascript:alert(1)',
])
def test_an_untrustworthy_referrer_falls_back(app, referrer):
    with app.test_request_context('/', headers={'Referer': referrer} if referrer else {}):
        assert _safe_back_url('/orders') == '/orders'


def test_a_referrer_from_this_site_is_honoured(app):
    with app.test_request_context(
            '/', headers={'Referer': 'http://localhost/orders/abc'}):
        assert _safe_back_url('/fallback') == 'http://localhost/orders/abc'


def test_a_relative_referrer_is_honoured(app):
    with app.test_request_context('/', headers={'Referer': '/orders/abc'}):
        assert _safe_back_url('/fallback') == '/orders/abc'


# --- through a real route ------------------------------------------------

def test_downloading_a_missing_file_without_a_referrer_goes_somewhere_real(
        client, login, a_document):
    """The old code sent the browser to a page called "None"."""
    login("admin")
    resp = client.get(f"/documents/{a_document['document_id']}/download")

    assert resp.status_code in (302, 303)
    assert resp.headers['Location'] not in (None, 'None'), (
        "the user must land on a real page after a failed download"
    )


def test_a_hostile_referrer_does_not_bounce_the_user_off_site(
        client, login, a_document):
    login("admin")
    resp = client.get(f"/documents/{a_document['document_id']}/download",
                      headers={'Referer': 'https://evil.com/steal'})

    assert 'evil.com' not in (resp.headers.get('Location') or ''), (
        "a referrer from another site must not be used as the return address"
    )


def test_no_route_redirects_to_a_bare_referrer():
    """Keeps the whole class out, not just the ten instances found.

    `redirect(request.referrer)` is the shape; `_safe_back_url(default)` is the
    replacement. One route builds its own same-origin check by hand because it
    needs the path and query as a `next` value — that one is checked by eye and
    left alone, so the lint looks only for the bare redirect.
    """
    import io
    import pathlib
    import re

    routes_dir = pathlib.Path(__file__).resolve().parents[1] / 'app' / 'routes'
    offenders = []
    for path in sorted(routes_dir.glob('*.py')):
        text = io.open(path, encoding='utf-8').read()
        for match in re.finditer(r'redirect\(\s*request\.referrer', text):
            line = text[:match.start()].count(chr(10)) + 1
            offenders.append(f'{path.name}:{line}')

    assert offenders == [], (
        "these redirect straight to the Referer header, which is absent for a "
        "user who opened the link directly (giving Location: None) and is set "
        f"by whoever sent them here: {offenders}"
    )
