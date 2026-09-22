"""Choosing standardization rules by ticking a grid.

Two things were missing, and they are the same thing seen from two sides.

There was no way to CREATE a rule. The screen listed whatever had been seeded
and let you edit those; a field nobody had thought of in advance could never be
configured. And the rule's target was shown as a bare `field_name` string, so
the answer to "how does the system know which field I mean" was "it does not —
somebody typed it once".

Both are answered by turning the screen into a matrix. Every text field of every
normalizable entity is a ROW, discovered from the data model rather than from a
seed list, and every primitive is a COLUMN. Ticking a cell applies that rule to
that field. There is no create form because there is nothing to create: the
field is already there, waiting.

Unticking every cell on a row removes the rule, which is the delete.

Fields that must never be rewritten - tax codes, document numbers, emails,
phone numbers - are listed but locked, so a user can see the system knows about
them and chose not to touch them, rather than wondering why they are absent.
"""
import pytest

from app.services.normalization_service import NormalizationService


def _field_names(rows):
    return [row['field_name'] for row in rows]


# --- discovering what can be configured ----------------------------------

def test_every_text_field_of_an_entity_is_offered(app, seed):
    """Not just the seeded ones: the data model is the source."""
    with app.app_context():
        rows = NormalizationService.configurable_fields('customer')
        names = _field_names(rows)

        assert 'name' in names
        assert 'address' in names
        assert 'representative_name' in names
        assert 'notes' in names, (
            'a field nobody seeded must still be configurable'
        )


def test_non_text_columns_are_not_offered(app, seed):
    """Normalizing a date or a foreign key is meaningless."""
    with app.app_context():
        names = _field_names(NormalizationService.configurable_fields('customer'))

        assert 'id' not in names
        assert 'company_id' not in names
        assert 'created_at' not in names
        assert 'is_active' not in names


def test_protected_fields_are_shown_but_locked(app, seed):
    """Absent would read as an oversight; locked reads as a decision."""
    with app.app_context():
        rows = {row['field_name']: row
                for row in NormalizationService.configurable_fields('customer')}

        assert 'tax_code' in rows
        assert rows['tax_code']['protected'] is True
        assert rows['name']['protected'] is False


def test_every_normalizable_entity_can_be_listed(app, seed):
    with app.app_context():
        for entity in ('customer', 'supplier', 'material', 'order'):
            assert NormalizationService.configurable_fields(entity), entity


def test_an_unknown_entity_yields_nothing_rather_than_raising(app, seed):
    with app.app_context():
        assert NormalizationService.configurable_fields('nope') == []


# --- the rules currently applied come back with the fields ---------------

def test_a_saved_rule_shows_on_its_field(app, seed):
    from app.config import db
    from app.models.models import NormalizationRule

    with app.app_context():
        db.session.add(NormalizationRule(
            company_id=seed['company_id'], entity_type='customer',
            field_name='notes', primitives=['trim', 'upper'],
            mode=NormalizationRule.MODE_AUTO, is_active=True))
        db.session.commit()

        rows = {row['field_name']: row
                for row in NormalizationService.configurable_fields(
                    'customer', company_id=seed['company_id'])}

        assert set(rows['notes']['primitives']) == {'trim', 'upper'}
        assert rows['notes']['mode'] == 'auto'
        assert rows['name']['primitives'] != ['trim', 'upper']


def test_another_company_rules_do_not_leak(app, seed):
    from app.config import db
    from app.models import Company
    from app.models.models import NormalizationRule

    with app.app_context():
        rival = Company(company_code='NRM', name='Rival', email='r@nrm.test')
        db.session.add(rival)
        db.session.flush()
        db.session.add(NormalizationRule(
            company_id=rival.id, entity_type='customer', field_name='notes',
            primitives=['upper'], mode='auto', is_active=True))
        db.session.commit()

        rows = {row['field_name']: row
                for row in NormalizationService.configurable_fields(
                    'customer', company_id=seed['company_id'])}
        assert rows['notes']['primitives'] == []


# --- ticking, retargeting and clearing -----------------------------------

def test_ticking_a_cell_creates_the_rule(app, client, login, seed):
    from app.models.models import NormalizationRule

    login('admin')
    client.post('/settings/standardization', data={
        'action': 'save_matrix',
        'entity': 'customer',
        'primitives_customer_notes': ['trim', 'title_case'],
        'mode_customer_notes': 'auto',
    }, follow_redirects=True)

    with app.app_context():
        rule = NormalizationRule.query.filter_by(
            company_id=seed['company_id'], entity_type='customer',
            field_name='notes').first()
        assert rule is not None, 'ticking a cell must create the rule'
        assert set(rule.primitives) == {'trim', 'title_case'}


def test_unticking_everything_removes_the_rule(app, client, login, seed):
    """Clearing a row is the delete; there is no separate delete button."""
    from app.config import db
    from app.models.models import NormalizationRule

    with app.app_context():
        db.session.add(NormalizationRule(
            company_id=seed['company_id'], entity_type='customer',
            field_name='notes', primitives=['upper'], mode='auto',
            is_active=True))
        db.session.commit()

    login('admin')
    client.post('/settings/standardization', data={
        'action': 'save_matrix',
        'entity': 'customer',
    }, follow_redirects=True)

    with app.app_context():
        assert NormalizationRule.query.filter_by(
            company_id=seed['company_id'], entity_type='customer',
            field_name='notes').first() is None


def test_a_protected_field_cannot_be_given_a_rule(app, client, login, seed):
    """Even when the form is crafted by hand."""
    from app.models.models import NormalizationRule

    login('admin')
    client.post('/settings/standardization', data={
        'action': 'save_matrix',
        'entity': 'customer',
        'primitives_customer_tax_code': ['upper'],
        'mode_customer_tax_code': 'auto',
    }, follow_redirects=True)

    with app.app_context():
        assert NormalizationRule.query.filter_by(
            company_id=seed['company_id'], entity_type='customer',
            field_name='tax_code').first() is None


def test_saving_one_entity_leaves_another_alone(app, client, login, seed):
    from app.config import db
    from app.models.models import NormalizationRule

    with app.app_context():
        db.session.add(NormalizationRule(
            company_id=seed['company_id'], entity_type='material',
            field_name='name', primitives=['trim'], mode='auto',
            is_active=True))
        db.session.commit()

    login('admin')
    client.post('/settings/standardization', data={
        'action': 'save_matrix', 'entity': 'customer',
    }, follow_redirects=True)

    with app.app_context():
        assert NormalizationRule.query.filter_by(
            company_id=seed['company_id'], entity_type='material',
            field_name='name').first() is not None


# --- the screen -----------------------------------------------------------

def test_the_screen_renders_a_cell_per_field_and_rule(client, login):
    login('admin')
    body = client.get('/settings/standardization').get_data(as_text=True)

    assert 'primitives_customer_name' in body
    assert 'primitives_customer_notes' in body


def test_the_screen_shows_the_technical_field_name(client, login):
    """Chosen deliberately: every text field, named as the system names it."""
    login('admin')
    body = client.get('/settings/standardization').get_data(as_text=True)
    assert 'representative_name' in body


def test_a_protected_field_renders_without_a_tickable_box(client, login):
    login('admin')
    body = client.get('/settings/standardization').get_data(as_text=True)

    assert 'tax_code' in body
    assert 'primitives_customer_tax_code' not in body
