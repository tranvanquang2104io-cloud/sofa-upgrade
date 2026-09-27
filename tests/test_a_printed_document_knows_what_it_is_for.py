"""A printed document points at its source generically, not by a column per kind.

`Document` links back with one foreign key per document kind — `quotation_id`,
`contract_id`, `handover_record_id`, `payment_report_id`. Four kinds, four
columns. The framework agreement, the order confirmation, the purchase order
and the production plan have none, which is why printing them records nothing
and their screens show no history.

The owner, asking for this to be organised properly: *"sau này mở rộng thì sẽ
rất nhiều form in của rất nhiều loại chứng từ, phải làm sao để nó quản lý khoa
học và gọn gàng"*. A column per kind is the opposite: every new printable
document is a migration, a model change, a relationship, and a fifth branch in
every place that asks "what was this printed from?".

So: `source_type` + `source_id`, the shape `ApprovalRequest` and
`StockMovement` already use here. A new printable kind adds a row of data, not
a column of schema.

The four existing columns are kept and backfilled from, not dropped. They are
what today's relationships and screens read, and removing them in the same
change that introduces their replacement would mean one migration doing two
jobs — the one that moves data and the one that can be rolled back cheaply.
"""
import datetime as dt

import pytest


@pytest.fixture()
def agreement(app, seed):
    from app.config import db
    from app.models.models import MasterAgreement

    with app.app_context():
        record = MasterAgreement(
            company_id=seed['company_id'], customer_id=seed['customer_id'],
            agreement_number='HDNT-DOC',
            effective_from=dt.date(2026, 1, 1),
            status=MasterAgreement.STATUS_ACTIVE)
        db.session.add(record)
        db.session.commit()
        return {**seed, 'agreement_id': str(record.id)}


def test_a_document_can_name_a_source_of_any_kind(app, agreement):
    from app.config import db
    from app.models.models import Document

    with app.app_context():
        doc = Document(company_id=agreement['company_id'],
                       document_name='HDNT-DOC', document_type='agreement',
                       document_format='docx', file_path='x.docx',
                       source_type='master_agreement',
                       source_id=agreement['agreement_id'])
        db.session.add(doc)
        db.session.commit()

        found = Document.query.filter_by(
            source_type='master_agreement',
            source_id=agreement['agreement_id']).one()
        assert found.document_name == 'HDNT-DOC'


def test_documents_for_finds_them_whatever_the_kind(app, agreement):
    """One lookup for every printable thing, present and future."""
    from app.config import db
    from app.models.models import Document
    from app.services.printing import documents_for

    with app.app_context():
        from app.models.models import MasterAgreement
        record = MasterAgreement.query.get(agreement['agreement_id'])
        db.session.add(Document(
            company_id=agreement['company_id'], document_name='HDNT-1',
            document_type='agreement', document_format='docx',
            file_path='a.docx', source_type='master_agreement',
            source_id=record.id, generated_at=dt.datetime(2026, 9, 1)))
        db.session.add(Document(
            company_id=agreement['company_id'], document_name='HDNT-2',
            document_type='agreement', document_format='pdf',
            file_path='b.pdf', source_type='master_agreement',
            source_id=record.id, generated_at=dt.datetime(2026, 9, 5)))
        db.session.commit()

        found = documents_for(record)
        assert [d.document_name for d in found] == ['HDNT-2', 'HDNT-1'], (
            'newest first — the one somebody most likely wants is the one '
            f'they last sent: {[d.document_name for d in found]}')


def test_the_old_per_kind_links_still_work(app, seed):
    """The four existing columns are what today's screens read.

    Replacing them in the same change that introduces the generic pair would
    be one migration doing two jobs, and the rollback would take the data with
    it.
    """
    from app.config import db
    from app.models import Order
    from app.models.models import Document, Quotation
    from app.services.printing import documents_for

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-DOC',
                      title='Sofa góc L')
        db.session.add(order)
        db.session.flush()
        quotation = Quotation(company_id=seed['company_id'],
                              order_id=order.id, quotation_number='BG-DOC',
                              quotation_date=dt.date(2026, 9, 1),
                              total_amount=1_000_000)
        db.session.add(quotation)
        db.session.flush()
        db.session.add(Document(
            company_id=seed['company_id'], order_id=order.id,
            quotation_id=quotation.id, document_name='BG-DOC',
            document_type='quotation', document_format='docx',
            file_path='q.docx', generated_at=dt.datetime(2026, 9, 1)))
        db.session.commit()

        assert len(quotation.documents) == 1, 'the old relationship broke'
        # And the generic lookup finds it too, through the same columns.
        assert len(documents_for(quotation)) == 1, (
            'a document recorded the old way is invisible to the new lookup, '
            'so converging a screen would empty its history')


def test_an_unknown_object_returns_nothing_rather_than_raising(app, seed):
    """A screen asking about something unprintable gets an empty list.

    Raising would take down a page over a history block, which is the least
    important thing on it.
    """
    from app.models import Order
    from app.services.printing import documents_for

    with app.app_context():
        order = Order.query.filter_by(company_id=seed['company_id']).first()
        assert documents_for(object()) == []
