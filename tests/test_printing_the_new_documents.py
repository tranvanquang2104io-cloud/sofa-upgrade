"""Framework agreements and order confirmations must be printable.

The owner: "tất cả các chức năng mới: Hợp đồng nguyên tắc, PR, PO, GR,
Invoice … đều cần form in hết."

These two are the closest to done and the most consequential: a HĐNT is the
contract a customer signs, and an ĐĐH is what a VAT invoice is issued against.
Both already have variable collectors — `collect_master_agreement_variables`
and `collect_order_confirmation_variables`, written when the feature was built
— and neither had a branch in the generator, so nothing could reach them. The
work was three quarters finished and produced nothing.

Measured across the product while doing this, and recorded in §8.2: printing is
split in two. Quotation, contract, handover and payment go through the template
system, so a company can upload its own .docx. The purchase order and the
production plan are built in code, so their wording and letterhead cannot be
changed at all. That split is the thing to settle before adding more printers,
because only one of the two can carry the versioning the owner asked for.
"""
import datetime as dt
import io
import os

import pytest

# Files the fixtures write into the app's own template folder, removed after
# the run so they cannot be committed by accident again.
_ARTEFACTS = []


@pytest.fixture(autouse=True)
def _clean_up_written_templates():
    yield
    while _ARTEFACTS:
        try:
            os.remove(_ARTEFACTS.pop())
        except OSError:
            pass


@pytest.fixture()
def agreement(app, seed):
    from app.config import db
    from app.models.models import MasterAgreement

    with app.app_context():
        record = MasterAgreement(
            company_id=seed['company_id'], customer_id=seed['customer_id'],
            agreement_number='HDNT-PRINT',
            effective_from=dt.date(2026, 1, 1),
            scope_description='Cung cấp sofa và ghế theo từng đơn đặt hàng.',
            status=MasterAgreement.STATUS_ACTIVE)
        db.session.add(record)
        db.session.commit()
        return {**seed, 'agreement_id': str(record.id)}


@pytest.fixture()
def confirmation(app, seed):
    from app.config import db
    from app.models import Order
    from app.models.models import MasterAgreement, OrderConfirmation

    with app.app_context():
        parent = MasterAgreement(
            company_id=seed['company_id'], customer_id=seed['customer_id'],
            agreement_number='HDNT-FOR-DDH',
            effective_from=dt.date(2026, 1, 1),
            status=MasterAgreement.STATUS_ACTIVE)
        db.session.add(parent)
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-PRINT',
                      title='Sofa góc L')
        db.session.add(order)
        db.session.flush()
        record = OrderConfirmation(
            company_id=seed['company_id'], order_id=order.id,
            master_agreement_id=parent.id,
            confirmation_number='DDH-PRINT',
            confirmation_date=dt.date(2026, 9, 1),
            items=[{'name': 'Sofa góc L', 'quantity': 1, 'unit': 'bộ',
                    'unit_price': 40_000_000, 'total': 40_000_000}],
            subtotal=40_000_000, vat_rate=8, vat_amount=3_200_000,
            total_amount=43_200_000,
            status=OrderConfirmation.STATUS_CONFIRMED)
        db.session.add(record)
        db.session.commit()
        return {**seed, 'order_id': str(order.id),
                'confirmation_id': str(record.id)}


def _install_template(app, company_id, doc_type, name):
    """A minimal .docx the engine can fill, so the test needs no fixture file.

    Written with a name the cleanup below removes: the first version left
    `agreement_test.docx` behind in the repository, and it was committed.
    """
    from docx import Document as Docx

    from app.config import db
    from app.models.models import DocumentTemplate

    folder = app.config['TEMPLATES_FOLDER']
    import os
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f'{doc_type}_test.docx')
    _ARTEFACTS.append(path)
    document = Docx()
    document.add_paragraph('{{ company_name }}')
    document.add_paragraph('{{ customer_name }}')
    document.save(path)

    with app.app_context():
        template = DocumentTemplate(
            company_id=company_id, name=name, document_type=doc_type,
            template_file=f'{doc_type}_test.docx', is_active=True)
        db.session.add(template)
        db.session.commit()


def test_a_framework_agreement_can_be_printed(app, client, login, agreement):
    pytest.importorskip('docx')
    _install_template(app, agreement['company_id'], 'agreement',
                      'HĐNT mẫu')

    login('admin')
    response = client.post(
        f"/documents/generate/agreement/{agreement['agreement_id']}",
        data={'format': 'docx'}, follow_redirects=True)
    assert response.status_code == 200

    from app.models.models import Document
    with app.app_context():
        assert Document.query.filter_by(document_type='agreement').first() \
            is not None, 'nothing was produced for a framework agreement'


def test_an_order_confirmation_can_be_printed(app, client, login,
                                              confirmation):
    pytest.importorskip('docx')
    _install_template(app, confirmation['company_id'], 'order_confirmation',
                      'ĐĐH mẫu')

    login('admin')
    response = client.post(
        f"/documents/generate/order_confirmation/{confirmation['confirmation_id']}",
        data={'format': 'docx'}, follow_redirects=True)
    assert response.status_code == 200

    from app.models.models import Document
    with app.app_context():
        assert Document.query.filter_by(
            document_type='order_confirmation').first() is not None, (
            'nothing was produced for an order confirmation')


def test_an_unknown_document_type_is_still_refused(app, client, login, seed):
    """Adding two types must not turn the generator into a free-for-all."""
    login('admin')
    response = client.post(
        '/documents/generate/not_a_type/00000000-0000-0000-0000-000000000000',
        follow_redirects=True)
    from app.utils.i18n import t
    assert t('Unknown document type') in response.get_data(as_text=True)
