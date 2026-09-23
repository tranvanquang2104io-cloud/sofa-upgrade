"""The standardization screen has the workflow screen's bug, in the same place.

The owner asked the same two questions about this screen: what are the two
sections for, and why is there no "create new"?

**The sections fight.** As on the workflow screen, saving the grid wrote
`is_active = True` on every row it touched, so an administrator who switched a
rule off in the list below, then saved the grid for an unrelated field, turned
it back on without being told. Here that means text starts being rewritten
again — silently, at the moment a record is saved.

**There is no "create new" because there is nothing to create.** The grid is
built from the data model: every text field of the entity is already a row,
whether or not a rule exists for it. Ticking a transform creates the rule and
clearing the row deletes it. That is a sound design and it is also invisible,
which is why it reads as a missing feature. The screen has to say so.
"""
import pytest

from app.models.models import NormalizationRule


@pytest.fixture()
def customer_rules(app, seed):
    """A rule on a customer field, set the way the grid sets one."""
    from app.config import db

    with app.app_context():
        rule = NormalizationRule(
            company_id=seed['company_id'], entity_type='customer',
            field_name='name', primitives=['title_case'],
            mode=NormalizationRule.MODE_AUTO, is_active=True)
        db.session.add(rule)
        db.session.commit()
    return seed


def _rule(app, company_id, field):
    with app.app_context():
        return NormalizationRule.query.filter_by(
            company_id=company_id, entity_type='customer',
            field_name=field).first()


def _post_grid(client, app, company_id):
    """Save the grid from its current state, as the screen does."""
    with app.app_context():
        current = NormalizationRule.query.filter_by(
            company_id=company_id, entity_type='customer').all()
        data = {'action': 'save_matrix', 'entity': 'customer'}
        for rule in current:
            key = f'primitives_customer_{rule.field_name}'
            data.setdefault(key, [])
            data[key] = list(rule.primitives or [])
            data[f'mode_customer_{rule.field_name}'] = rule.mode
    return client.post('/settings/standardization', data=data,
                       follow_redirects=True)


def test_saving_the_grid_does_not_switch_a_disabled_rule_back_on(
        app, client, login, customer_rules):
    from app.config import db

    company_id = customer_rules['company_id']
    with app.app_context():
        rule = NormalizationRule.query.filter_by(
            company_id=company_id, field_name='name').first()
        rule.is_active = False
        db.session.commit()

    login('admin')
    _post_grid(client, app, company_id)

    assert _rule(app, company_id, 'name').is_active is False, (
        'saving the grid started rewriting text again, using a rule the '
        'administrator had switched off'
    )


def test_clearing_a_row_stops_that_field_being_normalized(app, client, login,
                                                          customer_rules):
    """And it has to STAY cleared.

    Clearing used to delete the row, and the screen seeds the defaults whenever
    a company has no rows at all — so a company that deliberately cleared
    everything had it switched back on the next time anyone opened the page,
    silently, and text started being rewritten again on save.

    What matters to a user is the field, not the row: assert the guarantee, not
    the implementation that happened to provide it.
    """
    company_id = customer_rules['company_id']

    login('admin')
    client.post('/settings/standardization',
                data={'action': 'save_matrix', 'entity': 'customer'},
                follow_redirects=True)

    rule = _rule(app, company_id, 'name')
    assert rule is None or not rule.is_active or not rule.primitives, (
        'the field is still being normalized after its row was cleared')

    # Reopen the screen: the defaults must not come back.
    client.get('/settings/standardization')
    rule = _rule(app, company_id, 'name')
    assert rule is None or not rule.is_active or not rule.primitives, (
        'reopening the screen restored the default rule the company had cleared'
    )


def test_the_screen_explains_why_there_is_no_create_button(client, login,
                                                           seed):
    """A sound design that is invisible reads as a missing feature."""
    login('admin')
    body = client.get('/settings/standardization').get_data(as_text=True)
    assert 'Mỗi trường văn bản đã là một dòng sẵn' in body, (
        'the screen does not say why it has no "create new"'
    )
