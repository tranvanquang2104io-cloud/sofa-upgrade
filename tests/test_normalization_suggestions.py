"""The confirm mode promised a suggestion and never made one.

The standardization settings screen tells the admin that a `confirm` rule is
"suggested only — the value is never rewritten without a person agreeing". The
first half was true: nothing was rewritten. The second half never happened.
`normalize_instance()` returns the pending suggestions and its only caller, the
ORM listener, dropped them on the floor.

So `confirm` was a safe no-op: choosing it looked like choosing caution and was
actually choosing nothing.

Delivered smaller than the "suggestion inbox" in the plan, deliberately. A
queue you have to remember to visit is the wrong shape for a shop owner; the
moment the suggestion is useful is right after saving, where they still have
the record in mind. No new table, and the value is still never rewritten on its
own.
"""
import pytest


@pytest.fixture()
def confirm_rule(app, seed):
    """A confirm-mode rule that title-cases a customer's name."""
    from app.config import db
    from app.models.models import NormalizationRule

    with app.app_context():
        db.session.add(NormalizationRule(
            company_id=seed['company_id'], entity_type='customer',
            field_name='name', primitives=['title_case'],
            mode=NormalizationRule.MODE_CONFIRM, is_active=True))
        db.session.commit()
        return seed


def test_a_confirm_rule_still_never_rewrites_the_value(app, confirm_rule):
    """The half that already worked must keep working."""
    from app.config import db
    from app.models import Customer

    with app.app_context():
        c = Customer(company_id=confirm_rule['company_id'],
                     store_id=confirm_rule['store_id'],
                     customer_code='KH-SUG', name='nguyễn văn a')
        db.session.add(c)
        db.session.commit()

        assert Customer.query.get(c.id).name == 'nguyễn văn a'


def test_the_suggestion_is_recorded_for_the_request(app, confirm_rule):
    from flask import g

    from app.config import db
    from app.models import Customer
    from app.services.normalization_service import pending_suggestions

    with app.test_request_context('/'):
        c = Customer(company_id=confirm_rule['company_id'],
                     store_id=confirm_rule['store_id'],
                     customer_code='KH-SUG2', name='nguyễn văn a')
        db.session.add(c)
        db.session.commit()

        suggestions = pending_suggestions()
        assert len(suggestions) == 1
        assert suggestions[0]['original'] == 'nguyễn văn a'
        assert suggestions[0]['suggested'] == 'Nguyễn Văn A'


def test_an_auto_rule_produces_no_suggestion(app, seed):
    """Auto rules just apply; there is nothing to agree to."""
    from app.config import db
    from app.models import Customer
    from app.models.models import NormalizationRule
    from app.services.normalization_service import pending_suggestions

    with app.test_request_context('/'):
        db.session.add(NormalizationRule(
            company_id=seed['company_id'], entity_type='customer',
            field_name='name', primitives=['title_case'],
            mode=NormalizationRule.MODE_AUTO, is_active=True))
        db.session.commit()

        c = Customer(company_id=seed['company_id'], store_id=seed['store_id'],
                     customer_code='KH-AUTO', name='nguyễn văn a')
        db.session.add(c)
        db.session.commit()

        assert pending_suggestions() == []
        assert Customer.query.get(c.id).name == 'Nguyễn Văn A'


def test_a_value_already_in_shape_suggests_nothing(app, confirm_rule):
    from app.config import db
    from app.models import Customer
    from app.services.normalization_service import pending_suggestions

    with app.test_request_context('/'):
        c = Customer(company_id=confirm_rule['company_id'],
                     store_id=confirm_rule['store_id'],
                     customer_code='KH-OK', name='Nguyễn Văn A')
        db.session.add(c)
        db.session.commit()

        assert pending_suggestions() == []


def test_the_user_is_told_after_saving(app, client, login, confirm_rule):
    """Through a real screen: create a customer, see the suggestion."""
    login("admin")
    body = client.post('/customers/create', data={
        'customer_code': 'KH-FORM',
        'name': 'trần thị bình',
        'store_id': str(confirm_rule['store_id']),
    }, follow_redirects=True).get_data(as_text=True)

    assert 'Trần Thị Bình' in body, (
        "the suggested spelling must reach the person who typed it"
    )


def test_nothing_is_said_when_there_is_nothing_to_suggest(app, client, login,
                                                           confirm_rule):
    login("admin")
    body = client.post('/customers/create', data={
        'customer_code': 'KH-QUIET',
        'name': 'Lê Văn Cường',
        'store_id': str(confirm_rule['store_id']),
    }, follow_redirects=True).get_data(as_text=True)

    # Match the suggestion message itself, not the words "chuẩn hóa" — those
    # also name the Data Standardization screen in the navigation bar, which
    # is on every page.
    assert 'nên viết là' not in body.lower()
