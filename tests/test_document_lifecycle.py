"""Which generated file is the one to send the customer?

Every regeneration writes a NEW file, because the generated name carries a
timestamp. One contract can therefore own three files, and before this the
screen marked only `loop.first` as "Latest" — but that list mixes document
TYPES, so the current contract could appear unmarked next to a newer payment
file. For staff who are not confident with computers, "which of these do I
send?" is a real question with a wrong answer available.

The status is also where a signing step will live: a signed document is
evidence and must never be silently replaced by a regeneration.
"""
import datetime as dt

import pytest

from app.models.models import Document


@pytest.fixture()
def order_with_docs(app, seed):
    """An order with a contract and a quotation, each with one document."""
    from app.config import db
    from app.models import Order
    from app.models.models import Contract, DocumentTemplate, Quotation

    with app.app_context():
        o = Order(company_id=seed["company_id"], store_id=seed["store_id"],
                  customer_id=seed["customer_id"], order_code="ORD-DOCS",
                  title="Docs")
        db.session.add(o)
        db.session.flush()
        q = Quotation(company_id=seed["company_id"], order_id=o.id,
                      quotation_number="QT-D1",
                      quotation_date=dt.date(2026, 1, 1), total_amount=0)
        c = Contract(company_id=seed["company_id"], order_id=o.id,
                     contract_number="CT-D1",
                     contract_date=dt.date(2026, 1, 2), contract_value=0)
        tpl = DocumentTemplate(company_id=seed["company_id"], name="T",
                              document_type="contract", template_file="t.docx")
        db.session.add_all([q, c, tpl])
        db.session.commit()
        return {'order_id': str(o.id), 'quotation_id': str(q.id),
                'contract_id': str(c.id), 'template_id': str(tpl.id),
                **seed}


def _add_doc(app, ctx, doc_type, name, **links):
    from app.config import db

    with app.app_context():
        d = Document(company_id=ctx["company_id"], order_id=ctx["order_id"],
                     template_id=ctx["template_id"], document_name=name,
                     document_type=doc_type, document_format='docx',
                     file_path=f'/tmp/{name}.docx', **links)
        db.session.add(d)
        db.session.commit()
        return str(d.id)


# --- the default ----------------------------------------------------------

def test_a_new_document_starts_as_current(app, order_with_docs):
    doc_id = _add_doc(app, order_with_docs, 'contract', 'HopDong_1',
                      contract_id=order_with_docs['contract_id'])
    with app.app_context():
        d = Document.query.get(doc_id)
        assert d.status == Document.STATUS_CURRENT
        assert d.is_current is True
        assert d.is_signed is False


# --- regeneration ---------------------------------------------------------

def test_regenerating_supersedes_the_previous_file(app, order_with_docs):
    """Two contract files, only one is the one to send."""
    from app.services.services import DocumentService

    first = _add_doc(app, order_with_docs, 'contract', 'HopDong_1',
                     contract_id=order_with_docs['contract_id'])

    with app.app_context():
        DocumentService()._supersede_previous(
            order_id=order_with_docs['order_id'], document_type='contract',
            contract_id=order_with_docs['contract_id'])
        from app.config import db
        db.session.commit()

        assert Document.query.get(first).status == Document.STATUS_SUPERSEDED


def test_regenerating_a_contract_leaves_other_document_types_alone(
        app, order_with_docs):
    """Scoped to the source document, not to the whole order."""
    from app.config import db
    from app.services.services import DocumentService

    quote_doc = _add_doc(app, order_with_docs, 'quotation', 'BaoGia_1',
                         quotation_id=order_with_docs['quotation_id'])
    _add_doc(app, order_with_docs, 'contract', 'HopDong_1',
             contract_id=order_with_docs['contract_id'])

    with app.app_context():
        DocumentService()._supersede_previous(
            order_id=order_with_docs['order_id'], document_type='contract',
            contract_id=order_with_docs['contract_id'])
        db.session.commit()

        assert Document.query.get(quote_doc).status == Document.STATUS_CURRENT, (
            "regenerating the contract must not touch the quotation's file"
        )


def test_a_signed_document_is_never_superseded(app, order_with_docs):
    """A signed document is evidence; a new draft must not replace it."""
    from app.config import db
    from app.services.services import DocumentService

    signed = _add_doc(app, order_with_docs, 'contract', 'HopDong_signed',
                      contract_id=order_with_docs['contract_id'])
    with app.app_context():
        d = Document.query.get(signed)
        d.status = Document.STATUS_SIGNED
        db.session.commit()

        DocumentService()._supersede_previous(
            order_id=order_with_docs['order_id'], document_type='contract',
            contract_id=order_with_docs['contract_id'])
        db.session.commit()

        assert Document.query.get(signed).status == Document.STATUS_SIGNED


def test_a_signed_document_counts_as_current(app, order_with_docs):
    from app.config import db

    doc_id = _add_doc(app, order_with_docs, 'contract', 'HopDong_s',
                      contract_id=order_with_docs['contract_id'])
    with app.app_context():
        d = Document.query.get(doc_id)
        d.status = Document.STATUS_SIGNED
        db.session.commit()
        assert Document.query.get(doc_id).is_current is True


# --- what the user sees ---------------------------------------------------

def test_the_screen_marks_the_current_file_of_each_type(app, client, login,
                                                        order_with_docs):
    """The old `loop.first` badge could leave the current contract unmarked."""
    from app.config import db

    _add_doc(app, order_with_docs, 'quotation', 'BaoGia_1',
             quotation_id=order_with_docs['quotation_id'])
    _add_doc(app, order_with_docs, 'contract', 'HopDong_1',
             contract_id=order_with_docs['contract_id'])

    login("admin")
    body = client.get(f"/documents/{order_with_docs['order_id']}").get_data(
        as_text=True)

    # both are current, so both should carry the badge
    assert body.count('Current version') + body.count('Bản hiện hành') >= 2, (
        "each document type should show its own current file"
    )


def test_a_replaced_file_is_visibly_marked(app, client, login, order_with_docs):
    from app.config import db

    old = _add_doc(app, order_with_docs, 'contract', 'HopDong_old',
                   contract_id=order_with_docs['contract_id'])
    with app.app_context():
        d = Document.query.get(old)
        d.status = Document.STATUS_SUPERSEDED
        db.session.commit()

    login("admin")
    body = client.get(f"/documents/{order_with_docs['order_id']}").get_data(
        as_text=True)
    assert 'Replaced' in body or 'Đã thay thế' in body


def test_a_document_with_no_recorded_size_does_not_break_the_page(
        app, client, login, order_with_docs):
    """A missing file_size used to divide None by 1024 and 500 the page."""
    _add_doc(app, order_with_docs, 'contract', 'HopDong_nosize',
             contract_id=order_with_docs['contract_id'])

    login("admin")
    resp = client.get(f"/documents/{order_with_docs['order_id']}")
    assert resp.status_code == 200, "a row with no size must not crash the list"
