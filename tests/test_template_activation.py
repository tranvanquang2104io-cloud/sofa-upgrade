"""Which .docx does a printed document actually come from?

`get_default_for_type()` answered that with `.first()` on a filtered query and
no ordering at all, while the settings screen let any number of templates of
the same type be Active at once — activating one never deactivated the other.

So a user who uploads a corrected contract template and activates it could
keep printing the OLD one, decided by whatever order the database happened to
return rows in, with nothing on screen to show which was in force. That is the
worst shape a bug can take for a non-technical user: no error, wrong paper.
"""
import pytest


def _tpl(db, company_id, name, doc_type='contract', active=True):
    from app.models.models import DocumentTemplate

    tpl = DocumentTemplate(company_id=company_id, name=name,
                           document_type=doc_type, template_file=f'/tmp/{name}',
                           is_active=active)
    db.session.add(tpl)
    return tpl


@pytest.fixture()
def two_active_templates(app, seed):
    """The state the old screen allowed: two Active contract templates."""
    from app.config import db

    with app.app_context():
        old = _tpl(db, seed['company_id'], 'Hop dong CU')
        db.session.flush()
        new = _tpl(db, seed['company_id'], 'Hop dong MOI')
        db.session.commit()
        return {'old_id': str(old.id), 'new_id': str(new.id), **seed}


def test_only_one_template_of_a_type_can_be_active(app, client, login,
                                                   two_active_templates):
    """Activating a template retires the one it replaces."""
    from app.models.models import DocumentTemplate

    login("admin")
    client.post(f"/settings/templates/{two_active_templates['new_id']}/activate")

    with app.app_context():
        actives = DocumentTemplate.query.filter_by(
            company_id=two_active_templates['company_id'],
            document_type='contract', is_active=True).all()
        assert [t.name for t in actives] == ['Hop dong MOI']


def test_activating_does_not_touch_another_document_type(app, client, login,
                                                          two_active_templates):
    """A contract template must not retire the quotation template."""
    from app.config import db
    from app.models.models import DocumentTemplate

    with app.app_context():
        _tpl(db, two_active_templates['company_id'], 'Bao gia', 'quotation')
        db.session.commit()

    login("admin")
    client.post(f"/settings/templates/{two_active_templates['new_id']}/activate")

    with app.app_context():
        quote = DocumentTemplate.query.filter_by(
            company_id=two_active_templates['company_id'],
            document_type='quotation').first()
        assert quote.is_active is True


def test_activating_does_not_reach_another_company(app, client, login,
                                                    two_active_templates):
    from app.config import db
    from app.models import Company
    from app.models.models import DocumentTemplate

    with app.app_context():
        rival = Company(company_code="TPL", name="Rival", email="r@tpl.test")
        db.session.add(rival)
        db.session.flush()
        _tpl(db, rival.id, 'Hop dong cua doi thu')
        rival_id = rival.id
        db.session.commit()

    login("admin")
    client.post(f"/settings/templates/{two_active_templates['new_id']}/activate")

    with app.app_context():
        other = DocumentTemplate.query.filter_by(company_id=rival_id).first()
        assert other.is_active is True


def test_the_default_lookup_is_deterministic_for_existing_data(
        app, two_active_templates):
    """Rows created before the exclusivity rule can still be doubly active.

    The lookup must not leave that to row order: the most recently created
    active template is the one a user last chose, so it wins.
    """
    from app.repositories.repository import DocumentTemplateRepository

    with app.app_context():
        picked = DocumentTemplateRepository().get_default_for_type(
            two_active_templates['company_id'], 'contract')
        assert picked.name == 'Hop dong MOI'
