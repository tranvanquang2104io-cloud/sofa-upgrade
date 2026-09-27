"""Two print buttons in the product cannot succeed, and nothing said so.

`generate_agreement_document` raises "No agreement template found for company"
(`services.py:1838`) and `generate_order_confirmation_document` raises "No
order confirmation template found" (`:1874`). Both are correct: printing needs
a template.

The template upload form offers seven document types
(`settings/templates.html:151-157`) and `agreement` and `order_confirmation`
are not among them. There is no other way to create one — no seed, no
management screen, no API.

So a company admin who presses "In HĐNT" gets an error, goes to the template
screen to fix it, and finds the type they need is not on the list. The feature
is not slow or awkward; it cannot be completed at all. Nobody noticed because
the two halves are in different files and each is individually correct.

This is the naming-based blind spot again, in its eighth form in this repo: a
hand-written list somewhere that has to agree with another hand-written list
somewhere else, and no third thing checking that they do.

So the list stops being hand-written twice. `PRINTABLE_TYPES` in
`app/services/printing.py` is the one source, the form renders from it, the
upload validates against it, and the test below asserts that every type the
CODE asks for is a type the UI can supply.
"""
import pytest


def test_every_type_the_code_requires_can_be_uploaded():
    """The two hand-written lists must agree, checked by a third thing.

    Read from the source rather than exercised, deliberately: the failure is
    a type the product needs and the form never offers, and no behavioural
    test can discover a type nobody wrote a path for.
    """
    import pathlib
    import re

    from app.services.printing import PRINTABLE_TYPES

    services = (pathlib.Path(__file__).resolve().parent.parent
                / 'app' / 'services' / 'services.py').read_text(
                    encoding='utf-8')

    required = set(re.findall(r"get_default_for_type\(\s*company_id,\s*'([a-z_]+)'",
                              services))
    required |= set(re.findall(r"get_default_for_type\(\s*\n?\s*company_id,\s*\n?\s*'([a-z_]+)'",
                               services))

    offered = {key for key, _ in PRINTABLE_TYPES}
    missing = sorted(required - offered)

    assert not missing, (
        f'the code requires a template of these types but the upload form '
        f'cannot create one: {missing}. Pressing the print button fails, and '
        f'the screen that would fix it does not offer the type.')


def test_the_upload_form_offers_every_printable_type(app, client, login):
    """Rendered, not just declared: the list must reach the screen."""
    from app.services.printing import PRINTABLE_TYPES

    login('admin')
    body = client.get('/settings/templates').get_data(as_text=True)

    for key, _label in PRINTABLE_TYPES:
        assert f'value="{key}"' in body, (
            f'the template upload form does not offer "{key}", so no '
            f'template of that type can ever be created')


def test_an_unknown_type_is_refused(app, client, login):
    """The validation and the form read the same list.

    Without this the form could be narrowed and the endpoint would still
    accept anything, which is how a type ends up in the database that no
    screen can see or manage.
    """
    import io

    from app.models.models import DocumentTemplate

    login('admin')
    client.post('/settings/templates/upload', data={
        'name': 'Mau bia dat',
        'document_type': 'not_a_real_type',
        'template_file': (io.BytesIO(b'x'), 'x.docx'),
    }, content_type='multipart/form-data', follow_redirects=True)

    with app.app_context():
        assert DocumentTemplate.query.filter_by(
            document_type='not_a_real_type').first() is None, (
            'a template was stored under a type nothing can print')


def test_an_agreement_template_can_now_be_uploaded_and_used(app, client,
                                                            login, seed):
    """The whole point, end to end: upload the type, then print with it."""
    pytest.importorskip('docx')

    import io as _io
    import os

    from docx import Document as Docx

    from app.models.models import DocumentTemplate

    buffer = _io.BytesIO()
    built = Docx()
    built.add_paragraph('{{ company_name }}')
    built.save(buffer)
    buffer.seek(0)

    login('admin')
    client.post('/settings/templates/upload', data={
        'name': 'HDNT mau chuan',
        'document_type': 'agreement',
        'template_file': (buffer, 'hdnt.docx'),
    }, content_type='multipart/form-data', follow_redirects=True)

    with app.app_context():
        stored = DocumentTemplate.query.filter_by(
            document_type='agreement', is_active=True).first()
        assert stored is not None, (
            'a company admin still cannot create the template the product '
            'demands before it will print a framework agreement')
        # Asserted through the resolver printing actually uses, not by
        # guessing the layout: uploads land in a per-company subfolder while
        # only the bare filename is stored, and `_get_template_file_path`
        # (services.py:1442) is what reconciles the two. Checking a path I
        # assumed would have tested my assumption instead of the product —
        # my first version of this line did exactly that and failed while the
        # feature worked.
        from app.services.services import DocumentService

        resolved = DocumentService()._get_template_file_path(stored)
        assert os.path.exists(resolved), (
            f'printing cannot find the template that was just uploaded '
            f'({resolved})')
