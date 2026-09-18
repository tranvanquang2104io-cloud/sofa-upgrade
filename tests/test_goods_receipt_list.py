"""Page 2 of the goods receipts.

The route paginated — 20 per page — and the template included the pagination
nav, but the route never passed `pagination` to the template. The include
renders nothing without it, so the nav silently never appeared and receipt 21
onwards was unreachable from the screen. Nothing looked broken: the page just
ended.
"""
import datetime as dt

import pytest


@pytest.fixture()
def many_receipts(app, seed):
    """25 receipts — more than one page of 20."""
    from app.config import db
    from app.models.models import GoodsReceipt

    with app.app_context():
        for i in range(1, 26):
            db.session.add(GoodsReceipt(
                company_id=seed['company_id'],
                store_id=seed['store_id'], gr_number=f'PN-{i:03d}',
                receipt_date=dt.date(2026, 1, 1)))
        db.session.commit()
        return seed


def test_the_first_page_shows_twenty(client, login, many_receipts):
    login("admin")
    body = client.get('/goods-receipts').get_data(as_text=True)
    assert body.count('PN-0') >= 20


def test_the_pagination_nav_is_rendered(client, login, many_receipts):
    """Without `pagination` in the context the include emits nothing at all."""
    login("admin")
    body = client.get('/goods-receipts').get_data(as_text=True)
    assert 'page=2' in body, "there must be a way to reach the second page"


def test_page_two_shows_the_rest(client, login, many_receipts):
    """25 receipts, newest first: page 1 holds PN-025..PN-006, page 2 the rest."""
    login("admin")
    body = client.get('/goods-receipts?page=2').get_data(as_text=True)
    assert 'PN-001' in body


def test_paging_never_repeats_or_drops_a_receipt(client, login, many_receipts):
    """End-to-end check that the two pages partition the receipts.

    Honest caveat: this passes on SQLite even without a tiebreaker, because
    SQLite happens to return insertion order for tied rows. It is kept as a
    statement of the behaviour users depend on, not as proof of the fix — the
    ordering contract itself is pinned by the test below, which does bite.
    """
    import re

    login("admin")
    seen = []
    for page in (1, 2):
        body = client.get(f'/goods-receipts?page={page}').get_data(as_text=True)
        seen += re.findall(r'PN-\d{3}', body)

    assert len(seen) == len(set(seen)), "a receipt appeared on two pages"
    assert len(set(seen)) == 25, "some receipts are on no page at all"


def test_receipts_do_not_cross_tenants(app, client, login, many_receipts):
    from app.config import db
    from app.models import Company, Store
    from app.models.models import GoodsReceipt

    with app.app_context():
        c = Company(company_code="GRR", name="Rival", email="r@grr.test")
        db.session.add(c)
        db.session.flush()
        st = Store(company_id=c.id, store_code="GRS", name="S")
        db.session.add(st)
        db.session.flush()
        db.session.add(GoodsReceipt(company_id=c.id,
                                    store_id=st.id, gr_number='ZZ-RIVAL-GR',
                                    receipt_date=dt.date(2026, 1, 1)))
        db.session.commit()

    login("admin")
    body = client.get('/goods-receipts').get_data(as_text=True)
    assert 'ZZ-RIVAL-GR' not in body


def test_the_receipt_ordering_has_a_tiebreaker():
    """created_at alone is not a stable sort.

    Receipts entered in the same second tie, and on an engine that does not
    guarantee an order for tied rows (PostgreSQL does not) LIMIT/OFFSET paging
    can show one receipt on both pages while another appears on neither. SQLite
    masks that at runtime, so the contract is asserted on the query itself.
    """
    import inspect

    from app.services.procurement_service import ProcurementService

    ordering = inspect.getsource(ProcurementService.list_grs).split('order_by')[1]
    assert 'gr_number' in ordering, (
        "the goods-receipt listing must break created_at ties on a unique "
        "column, or paging is not deterministic"
    )
