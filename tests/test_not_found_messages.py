"""Eight screens that bounced you back and said nothing.

The sales side answers a record you may not see with "Order not found or access
denied". The procurement side, for the same situation, redirected to the list
with no message at all: you click, the page changes, and nothing tells you why
what you asked for did not happen.

That is the same defect as the production norm that claimed a save it had not
made — the system knows the answer and does not say it. For a user who cannot
open a log or read a URL, a silent bounce is indistinguishable from a bug in
the app, and the usual next move is to try again.

These cover the ids being absent. Whether the record belongs to another company
is covered by tests/test_tenant_isolation_sweep.py; both arrive here the same
way, because _owned_po() and friends return None in either case.
"""
import uuid

import pytest

SILENT_ROUTES = [
    ('POST', '/purchase-orders/{id}/edit'),
    ('POST', '/purchase-orders/{id}/status/submit'),
    ('POST', '/purchase-orders/{id}/receive'),
    ('POST', '/requisitions/{id}/edit'),
    ('GET', '/requisitions/{id}'),
    ('POST', '/requisitions/{id}/status/submit'),
    ('POST', '/requisitions/{id}/convert'),
    ('GET', '/goods-receipts/{id}'),
]


@pytest.mark.parametrize("method,url_tpl", SILENT_ROUTES,
                         ids=[f"{m} {u}" for m, u in SILENT_ROUTES])
def test_a_record_you_cannot_see_says_so(client, login, method, url_tpl):
    login("admin")
    url = url_tpl.format(id=uuid.uuid4())

    send = client.post if method == 'POST' else client.get
    body = send(url, follow_redirects=True).get_data(as_text=True)

    assert ('không tìm thấy' in body.lower()
            or 'not found' in body.lower()
            or 'không có quyền' in body.lower()), (
        f"{method} {url_tpl} bounced the user back with no explanation"
    )


def test_no_handler_bounces_the_user_back_in_silence():
    """Keeps the class out, not just the eight instances.

    The shape is a guard that finds nothing and redirects with no flash in
    between. `abort()` is fine — that renders an error page the user can read.
    """
    import io as _io
    import pathlib
    import re

    routes = pathlib.Path(__file__).resolve().parents[1] / 'app' / 'routes'
    offenders = []
    for path in sorted(routes.glob('*.py')):
        text = _io.open(path, encoding='utf-8').read()
        lines = text.split(chr(10))
        for i, line in enumerate(lines):
            if not re.match(r"\s*if not [a-z_]+:\s*$", line):
                continue
            following = lines[i + 1:i + 3]
            redirects = any('return redirect' in x for x in following)
            speaks = any(('flash(' in x or 'abort(' in x) for x in following)
            if redirects and not speaks:
                offenders.append(f'{path.name}:{i + 1}')

    assert offenders == [], (
        "these send the user somewhere else without saying why, which reads as "
        f"a broken button: {offenders}"
    )

