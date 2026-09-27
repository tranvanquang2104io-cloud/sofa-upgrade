"""Replacing a print template rewrote history silently.

The owner asked for template management to be organised properly: *"chức năng
quản lý form in cũng cần khoa học và đầy đủ CRUD - vì sau này mở rộng thì sẽ
rất nhiều form in của rất nhiều loại chứng từ"*.

What was there: list, upload, activate, deactivate, and a conditional delete.
No edit, no way to look at a template before using it, and **no versions**.
Uploading a replacement deactivated the old row and inserted a new one with a
fresh random filename — so the old layout survived only as an inactive row
with nothing marking it as "the one that printed the contract we posted in
March".

Why that matters more than tidiness. A `Document` records `template_id`, so it
points at the row that produced it. But nothing stopped that row's FILE being
swapped, and nothing numbered the rows, so:

* the contract the customer holds cannot be reproduced;
* two contracts printed a month apart can look different with nothing
  explaining why;
* and an argument about what was agreed has no paper trail on our side.

Luật Kế toán 2015 Đ.27 again: a correction is recorded, never erased. A
template is the shape of the record, so replacing one is an event, not an
edit.

What is pinned here:

1. every template carries a version number, per company and document type;
2. uploading a replacement makes version N+1 and leaves N intact;
3. a document knows which VERSION printed it, not just which type;
4. the name and description can be edited freely — those describe the row, not
   the paper — but the FILE can never be swapped under a template that has
   already printed something;
5. an older version can be made current again, because "put back what we had
   in March" is a real request and the alternative is re-uploading a file
   somebody has to find.
"""
import io as _io

import pytest


def _docx_bytes(text='{{ company_name }}'):
    pytest.importorskip('docx')
    from docx import Document as Docx

    buffer = _io.BytesIO()
    built = Docx()
    built.add_paragraph(text)
    built.save(buffer)
    buffer.seek(0)
    return buffer


def _upload(client, doc_type='contract', name='Mau hop dong', text=None):
    return client.post('/settings/templates/upload', data={
        'name': name,
        'document_type': doc_type,
        'template_file': (_docx_bytes(text or '{{ company_name }}'),
                          'mau.docx'),
    }, content_type='multipart/form-data', follow_redirects=True)


def test_a_replacement_becomes_version_two_and_keeps_version_one(app, client,
                                                                 login):
    """The old layout survives, numbered, not just deactivated."""
    from app.models.models import DocumentTemplate

    login('admin')
    _upload(client, name='Hop dong ban dau')
    _upload(client, name='Hop dong sua lai')

    with app.app_context():
        rows = DocumentTemplate.query.filter_by(
            document_type='contract').order_by(
                DocumentTemplate.version).all()
        assert len(rows) == 2, f'expected two versions, got {len(rows)}'
        assert [row.version for row in rows] == [1, 2]
        assert rows[0].is_active is False
        assert rows[1].is_active is True, 'the newest version is not the one in use'


def test_a_document_records_which_version_printed_it(app, client, login,
                                                     seed):
    """`template_id` already pointed at a row; now that row has a number.

    Without the number, "which template made this?" answers with a uuid and a
    name that may since have been reused.
    """
    from app.models.models import Document, DocumentTemplate

    login('admin')
    _upload(client, doc_type='agreement', name='HDNT v1')

    with app.app_context():
        first = DocumentTemplate.query.filter_by(
            document_type='agreement', is_active=True).one()
        assert first.version == 1

    # ... print something with it, then replace the template
    from app.config import db
    from app.models.models import MasterAgreement
    import datetime as dt

    with app.app_context():
        record = MasterAgreement(
            company_id=seed['company_id'], customer_id=seed['customer_id'],
            agreement_number='HDNT-VER', effective_from=dt.date(2026, 1, 1),
            status=MasterAgreement.STATUS_ACTIVE)
        db.session.add(record)
        db.session.commit()
        agreement_id = str(record.id)

    client.post(f'/documents/generate/agreement/{agreement_id}',
                data={'format': 'docx'}, follow_redirects=True)
    _upload(client, doc_type='agreement', name='HDNT v2')

    with app.app_context():
        produced = Document.query.filter_by(
            document_type='agreement').first()
        assert produced is not None, 'nothing was printed'
        assert produced.template.version == 1, (
            'the document points at the wrong version, so the paper the '
            'customer holds cannot be reproduced')


def test_the_file_of_a_used_template_cannot_be_replaced_in_place(app, client,
                                                                 login, seed):
    """Editing the layout under a template that has printed is not an edit.

    It is a silent rewrite of what we claim we sent. Renaming is fine; the
    file is not.

    This test PASSED before the edit route existed, because there was nothing
    to swap the file with. That is green for the wrong reason and worth saying
    out loud: it starts meaning something the moment editing is possible, and
    it is the test that has to keep passing while the rest of this file goes
    from red to green.
    """
    import datetime as dt

    from app.config import db
    from app.models.models import DocumentTemplate, MasterAgreement

    login('admin')
    _upload(client, doc_type='agreement', name='HDNT goc')

    with app.app_context():
        record = MasterAgreement(
            company_id=seed['company_id'], customer_id=seed['customer_id'],
            agreement_number='HDNT-LOCK', effective_from=dt.date(2026, 1, 1),
            status=MasterAgreement.STATUS_ACTIVE)
        db.session.add(record)
        db.session.commit()
        agreement_id = str(record.id)

    client.post(f'/documents/generate/agreement/{agreement_id}',
                data={'format': 'docx'}, follow_redirects=True)

    with app.app_context():
        template = DocumentTemplate.query.filter_by(
            document_type='agreement', is_active=True).one()
        template_id, original_file = str(template.id), template.template_file

    client.post(f'/settings/templates/{template_id}/edit', data={
        'name': 'HDNT doi ten',
        'template_file': (_docx_bytes('{{ something_else }}'), 'khac.docx'),
    }, content_type='multipart/form-data', follow_redirects=True)

    with app.app_context():
        after = DocumentTemplate.query.get(template_id)
        assert after.template_file == original_file, (
            'the file behind a template that has already printed was swapped, '
            'so a document we sent can no longer be reproduced')


def test_renaming_a_template_is_allowed(app, client, login):
    """The name describes the row, not the paper."""
    from app.models.models import DocumentTemplate

    login('admin')
    _upload(client, name='Ten cu')

    with app.app_context():
        template = DocumentTemplate.query.filter_by(
            document_type='contract', is_active=True).one()
        template_id = str(template.id)

    client.post(f'/settings/templates/{template_id}/edit',
                data={'name': 'Ten moi', 'description': 'Ban dung cho 2026'},
                follow_redirects=True)

    with app.app_context():
        after = DocumentTemplate.query.get(template_id)
        assert after.name == 'Ten moi'
        assert after.description == 'Ban dung cho 2026'


def test_an_older_version_can_be_made_current_again(app, client, login):
    """"Put back what we had in March" is a real request."""
    from app.models.models import DocumentTemplate

    login('admin')
    _upload(client, name='Thang Ba')
    _upload(client, name='Thang Tu')

    with app.app_context():
        old = DocumentTemplate.query.filter_by(
            document_type='contract', version=1).one()
        old_id = str(old.id)

    client.post(f'/settings/templates/{old_id}/activate',
                follow_redirects=True)

    with app.app_context():
        assert DocumentTemplate.query.get(old_id).is_active is True
        newer = DocumentTemplate.query.filter_by(
            document_type='contract', version=2).one()
        assert newer.is_active is False, (
            'two versions of the same document type are active at once, so '
            'which one prints is whatever the query happens to return first')


def test_a_template_can_be_looked_at_before_it_is_used(app, client, login):
    """There was no way to see what a template contained.

    An admin with four contract templates and four names had to print a real
    contract to find out which was which.
    """
    from app.models.models import DocumentTemplate

    login('admin')
    _upload(client, name='Xem thu')

    with app.app_context():
        template_id = str(DocumentTemplate.query.filter_by(
            document_type='contract', is_active=True).one().id)

    response = client.get(f'/settings/templates/{template_id}/download')
    assert response.status_code == 200, (
        'a template cannot be opened, so the only way to see what it contains '
        'is to print a real document with it')
    assert len(response.data) > 0

