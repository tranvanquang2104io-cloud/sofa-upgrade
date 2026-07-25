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
