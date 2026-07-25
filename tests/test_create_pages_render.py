"""Smoke: create pages with item inputs still render after W15 edits."""


def test_quotation_create_page_renders(login, client, seeded_order):
    login(username="admin")
    resp = client.get(f"/quotations/{seeded_order['order_id']}/create")
    assert resp.status_code == 200
    assert b'name="item_quantity[]"' in resp.data


def test_order_create_page_renders(login, client):
    login(username="admin")
    resp = client.get("/orders/create")
    assert resp.status_code == 200
