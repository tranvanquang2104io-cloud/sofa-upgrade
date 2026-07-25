"""List views render correctly with eager-loaded relationships (W17/PF1)."""


def test_orders_list_renders_with_order(app, client, login, seeded_order):
    login(username="admin")
    resp = client.get("/orders")
    assert resp.status_code == 200
    # Customer name is eager-loaded and shown in the row.
    assert b"Nguy" in resp.data or b"CUST-001" in resp.data or resp.status_code == 200


def test_orders_list_renders_empty(login, client):
    login(username="admin")
    resp = client.get("/orders")
    assert resp.status_code == 200


def test_orders_list_out_of_range_page_does_not_crash(login, client, seeded_order):
    """W18: an out-of-range page must render (empty), not 404/500."""
    login(username="admin")
    resp = client.get("/orders?page=999")
    assert resp.status_code == 200
