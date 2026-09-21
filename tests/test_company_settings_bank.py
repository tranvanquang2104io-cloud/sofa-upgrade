"""Bank details that were discarded while the screen said "saved".

The bank-account rows are serialised by JavaScript into a hidden JSON field, so
in normal use the value is always well-formed. But the handler parsed it under
`except Exception: pass` and then flashed success unconditionally: any value it
could not read was dropped, the previous list was kept, and the user was told
their settings had been updated.

These details are printed on payment documents, so "silently kept the old ones"
is the wrong failure. Low likelihood, but the honest behaviour costs three
lines.
"""


def test_valid_bank_accounts_are_saved(app, client, login, seed):
    from app.models import Company

    login("admin")
    client.post('/settings/company', data={
        'name': 'Acme Sofa',
        'bank_accounts': '[{"bank_name": "LPBank", "account_number": "123",'
                         ' "account_holder": "Acme"}]',
    }, follow_redirects=True)

    with app.app_context():
        company = Company.query.get(seed['company_id'])
        assert company.bank_accounts[0]['bank_name'] == 'LPBank'


def test_unreadable_bank_accounts_do_not_report_success(app, client, login,
                                                        seed):
    login("admin")
    body = client.post('/settings/company', data={
        'name': 'Acme Sofa',
        'bank_accounts': '{not json at all',
    }, follow_redirects=True).get_data(as_text=True)

    assert 'Company settings updated successfully' not in body
    assert ('ngân hàng' in body.lower() or 'bank' in body.lower()), (
        "the user must be told which part could not be saved"
    )


def test_unreadable_bank_accounts_keep_the_previous_list(app, client, login,
                                                          seed):
    """Dropping them would be worse than refusing the change."""
    from app.config import db
    from app.models import Company

    with app.app_context():
        company = Company.query.get(seed['company_id'])
        company.bank_accounts = [{'bank_name': 'VCB', 'account_number': '999',
                                  'account_holder': 'Acme'}]
        db.session.commit()

    login("admin")
    client.post('/settings/company', data={
        'name': 'Acme Sofa', 'bank_accounts': '{not json at all',
    }, follow_redirects=True)

    with app.app_context():
        assert Company.query.get(seed['company_id']).bank_accounts[0][
            'bank_name'] == 'VCB'


def test_an_empty_field_clears_the_list(app, client, login, seed):
    from app.models import Company

    login("admin")
    client.post('/settings/company', data={'name': 'Acme Sofa',
                                           'bank_accounts': ''},
                follow_redirects=True)

    with app.app_context():
        assert Company.query.get(seed['company_id']).bank_accounts == []
