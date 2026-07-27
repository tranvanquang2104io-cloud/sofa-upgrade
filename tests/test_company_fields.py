"""Company template fields (business registration no., website)."""


def test_company_settings_saves_new_fields(app, login, client, seed):
    login(username="admin")
    client.post("/settings/company", data={
        "name": "Acme Sofa Co", "email": "a@acme.test",
        "business_registration_number": "GPKD-0123456",
        "website": "https://acme.test",
    }, follow_redirects=True)
    from app.models.models import Company
    with app.app_context():
        c = Company.query.get(seed["company_id"])
        assert c.business_registration_number == "GPKD-0123456"
        assert c.website == "https://acme.test"
