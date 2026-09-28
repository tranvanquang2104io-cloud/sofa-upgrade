"""The configuration screens for the workflow and standardization engines.

Both engines shipped with a working backend and no UI, which meant only a
developer could change them — the opposite of the point. These tests cover the
screens an administrator actually uses.
"""
import pytest


# --- workflow ------------------------------------------------------------

def test_workflow_page_seeds_rules_on_first_visit(app, client, login, seed):
    """The page must never be empty on a tenant that was never seeded."""
    from app.models.models import WorkflowRule

    login("admin")
    resp = client.get('/settings/workflow')
    assert resp.status_code == 200

    with app.app_context():
        assert WorkflowRule.query.filter_by(
            company_id=seed["company_id"]).count() > 0


def test_admin_can_relax_a_rule_through_the_page(app, client, login, seed):
    """The business scenario: take a deposit before the contract is signed."""
    from app.models.models import WorkflowRule
    from app.services.workflow_service import (
        ACTION_PAYMENT_ADVANCE, WorkflowService,
    )

    with app.app_context():
        WorkflowService.seed_defaults(seed["company_id"])
        rule = WorkflowRule.query.filter_by(
            company_id=seed["company_id"], action=ACTION_PAYMENT_ADVANCE).first()
        rule_id = str(rule.id)
        assert rule.mode == WorkflowRule.MODE_REQUIRED

    login("admin")
    resp = client.post('/settings/workflow', data={
        f'mode_{rule_id}': 'optional',
        f'active_{rule_id}': 'on',
        f'message_{rule_id}': '',
    }, follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        assert WorkflowRule.query.get(rule_id).mode == 'optional'


def test_workflow_page_rejects_an_unknown_mode(app, client, login, seed):
    """A hand-crafted POST must not be able to write a meaningless mode."""
    from app.models.models import WorkflowRule
    from app.services.workflow_service import WorkflowService

    with app.app_context():
        WorkflowService.seed_defaults(seed["company_id"])
        rule = WorkflowRule.query.filter_by(company_id=seed["company_id"]).first()
        rule_id, original = str(rule.id), rule.mode

    login("admin")
    client.post('/settings/workflow',
                data={f'mode_{rule_id}': 'whatever', f'active_{rule_id}': 'on'},
                follow_redirects=True)

    with app.app_context():
        assert WorkflowRule.query.get(rule_id).mode == original


def test_workflow_reset_restores_the_standard_process(app, client, login, seed):
    from app.config import db
    from app.models.models import WorkflowRule
    from app.services.workflow_service import WorkflowService

    with app.app_context():
        WorkflowService.seed_defaults(seed["company_id"])
        rule = WorkflowRule.query.filter_by(company_id=seed["company_id"]).first()
        rule_id = str(rule.id)
        rule.mode = 'optional'
        rule.is_active = False
        db.session.commit()

    login("admin")
    client.post('/settings/workflow', data={'action': 'reset'},
                follow_redirects=True)

    with app.app_context():
        restored = WorkflowRule.query.get(rule_id)
        assert restored.is_active is True


def test_workflow_settings_require_company_admin(client, login):
    """A store user must not be able to rewrite the company's process."""
    login("staff")
    resp = client.get('/settings/workflow', follow_redirects=False)
    # 403, exactly. `in (302, 403)` accepted a redirect too — an outcome this
    # route does not produce (measured), so the looser assertion bought
    # nothing and would have gone on passing if the guard ever degraded into
    # "bounce them to the login page", which looks the same to a test and
    # very different to a user who IS logged in.
    assert resp.status_code == 403, (
        f'a store user was not refused the workflow settings '
        f'(HTTP {resp.status_code})')


# --- standardization -----------------------------------------------------

def test_standardization_page_renders_with_a_preview(client, login, seed):
    login("admin")
    resp = client.get('/settings/standardization?sample=cty tnhh an phat')
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'CÔNG TY TNHH An Phat' in body or 'CÔNG TY' in body, (
        "the page should show what the configured rules would do to the sample"
    )


def test_admin_can_change_the_house_style_through_the_page(app, client, login,
                                                           seed):
    from app.models.models import NormalizationRule
    from app.services.normalization_service import NormalizationService

    with app.app_context():
        NormalizationService.seed_defaults(seed["company_id"])
        rule = NormalizationRule.query.filter_by(
            company_id=seed["company_id"], entity_type='customer',
            field_name='name').first()
        rule_id = str(rule.id)

    login("admin")
    client.post('/settings/standardization', data={
        f'active_{rule_id}': 'on',
        f'mode_{rule_id}': 'confirm',
        f'primitives_{rule_id}': ['nfc', 'trim', 'title_case'],
    }, follow_redirects=True)

    with app.app_context():
        updated = NormalizationRule.query.get(rule_id)
        assert updated.mode == 'confirm'
        assert updated.primitives == ['nfc', 'trim', 'title_case']


def test_standardization_page_ignores_unknown_primitives(app, client, login,
                                                         seed):
    """Only real transforms may be stored, whatever the form posts."""
    from app.models.models import NormalizationRule
    from app.services.normalization_service import NormalizationService

    with app.app_context():
        NormalizationService.seed_defaults(seed["company_id"])
        rule = NormalizationRule.query.filter_by(
            company_id=seed["company_id"]).first()
        rule_id = str(rule.id)

    login("admin")
    client.post('/settings/standardization', data={
        f'active_{rule_id}': 'on',
        f'mode_{rule_id}': 'auto',
        f'primitives_{rule_id}': ['trim', 'rm -rf', 'not_a_primitive'],
    }, follow_redirects=True)

    with app.app_context():
        assert NormalizationRule.query.get(rule_id).primitives == ['trim']


def test_standardization_settings_require_company_admin(client, login):
    login("staff")
    resp = client.get('/settings/standardization', follow_redirects=False)
    assert resp.status_code == 403, (
        f'a store user was not refused this settings screen '
        f'(HTTP {resp.status_code})')
