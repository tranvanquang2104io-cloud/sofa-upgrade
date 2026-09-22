"""Removing a document template that was uploaded by mistake.

The templates screen could upload, activate and deactivate, but never delete.
A file uploaded to the wrong document type, or a draft somebody was trying out,
stayed in the list for good — deactivating hides it from the generator but
leaves it on screen, so the list only grows.

Delete is not unconditional, and this is the line the owner drew: add CRUD
everywhere EXCEPT where it breaks a control. `Document.template_id` points at
the template a document was printed from, so deleting a template that has
produced documents would orphan that link and lose the answer to "what did this
contract come out of". A template with documents behind it therefore refuses
deletion and says to deactivate it instead — which is the operation that
actually fits that situation.
"""
import datetime as dt

import pytest


@pytest.fixture()
def template(app, seed):
    from app.config import db
    from app.models.models import DocumentTemplate

    with app.app_context():
        record = DocumentTemplate(
            company_id=seed['company_id'], name='Mẫu hợp đồng thử',
            document_type='contract', template_file='/tmp/thu.docx',
            is_active=False)
        db.session.add(record)
        db.session.commit()
        return {'template_id': str(record.id), **seed}


def _template(template_id):
    from app.models.models import DocumentTemplate
    return DocumentTemplate.query.get(template_id)


def test_an_unused_template_can_be_deleted(app, client, login, template):
    login('admin')
    client.post(f"/settings/templates/{template['template_id']}/delete",
                follow_redirects=True)

    with app.app_context():
        assert _template(template['template_id']) is None


def test_deleting_says_what_happened(client, login, template):
    login('admin')
    body = client.post(f"/settings/templates/{template['template_id']}/delete",
                       follow_redirects=True).get_data(as_text=True)
    assert ('đã xóa' in body.lower() or 'deleted' in body.lower())


def test_a_template_that_produced_documents_is_kept(app, client, login,
                                                    template):
    """Deleting it would orphan the link from every document it printed."""
    from app.config import db
    from app.models import Document, Order

    with app.app_context():
        order = Order(company_id=template['company_id'],
                      store_id=template['store_id'],
                      customer_id=template['customer_id'],
                      order_code='DH-TPL', title='Sofa')
        db.session.add(order)
        db.session.flush()
        db.session.add(Document(
            company_id=template['company_id'], order_id=order.id,
            template_id=template['template_id'], document_name='HD in thu',
            document_type='contract', document_format='pdf',
            file_path='/tmp/hd.pdf'))
        db.session.commit()

    login('admin')
    client.post(f"/settings/templates/{template['template_id']}/delete",
                follow_redirects=True)

    with app.app_context():
        assert _template(template['template_id']) is not None


def test_the_refusal_explains_and_offers_the_alternative(app, client, login,
                                                          template):
    """A refusal a user cannot act on is the same as a silent failure."""
    from app.config import db
    from app.models import Document, Order

    with app.app_context():
        order = Order(company_id=template['company_id'],
                      store_id=template['store_id'],
                      customer_id=template['customer_id'],
                      order_code='DH-TPL2', title='Sofa')
        db.session.add(order)
        db.session.flush()
        db.session.add(Document(
            company_id=template['company_id'], order_id=order.id,
            template_id=template['template_id'], document_name='HD in thu 2',
            document_type='contract', document_format='pdf',
            file_path='/tmp/hd2.pdf'))
        db.session.commit()

    login('admin')
    body = client.post(f"/settings/templates/{template['template_id']}/delete",
                       follow_redirects=True).get_data(as_text=True)

    assert 'chứng từ' in body.lower() or 'document' in body.lower()
    assert 'vô hiệu' in body.lower() or 'deactivate' in body.lower()


def test_another_company_template_cannot_be_deleted(app, client, login, seed):
    from app.config import db
    from app.models import Company
    from app.models.models import DocumentTemplate

    with app.app_context():
        rival = Company(company_code='TPD', name='Rival', email='r@tpd.test')
        db.session.add(rival)
        db.session.flush()
        stranger = DocumentTemplate(
            company_id=rival.id, name='Mẫu của đối thủ',
            document_type='contract', template_file='/tmp/rival.docx')
        db.session.add(stranger)
        db.session.commit()
        stranger_id = str(stranger.id)

    login('admin')
    client.post(f'/settings/templates/{stranger_id}/delete',
                follow_redirects=True)

    with app.app_context():
        assert _template(stranger_id) is not None


def test_the_screen_offers_delete_on_an_unused_template(client, login,
                                                        template):
    login('admin')
    body = client.get('/settings/templates').get_data(as_text=True)
    assert f"/settings/templates/{template['template_id']}/delete" in body


def test_deleting_asks_first(client, login, template):
    """It removes a file from disk; it cannot be undone."""
    login('admin')
    body = client.get('/settings/templates').get_data(as_text=True)

    index = body.find(f"/settings/templates/{template['template_id']}/delete")
    assert index != -1
    around = body[max(0, index - 400):index + 400]
    assert 'confirm(' in around or 'data-bs-toggle="modal"' in around
