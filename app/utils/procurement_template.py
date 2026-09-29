"""Turning the hardcoded purchase-order print into a template nobody has to code.

T-22a stopped those prints vanishing without a record. This is the other half:
making them Cách A, so the layout is a document an administrator can edit
rather than Python only a developer can change.

WHERE THE LAYOUT COMES FROM. Not from me. `build_purchase_order_docx` already
holds the exact form this business sends its suppliers — the headings, the
column order, the Vietnamese wording, the two signature blocks. This module
writes that same layout out as a .docx with `{{ }}` placeholders where the
values went. Nothing about the document is invented; it is the current print,
converted.

That distinction is the whole reason this could be done without asking for the
company's real form. Authoring a NEW layout would mean inventing how their
paperwork looks, which is not a thing to guess at. Reproducing the one already
in the code is not a guess.

The row loop is why this could not be done mechanically. `docxtpl` needs
`{%tr for ... %}` inside a table row, and there is no way to derive that from a
Python loop that appends rows one at a time — the template has to be written
knowing that a table row repeats. That is a small piece of authoring, and it is
the piece that made T-22b a separate task.

The generated template is a STARTING POINT, seeded once per company. After
that it is an ordinary DocumentTemplate: editable, versioned, and replaceable
by whatever form the company actually uses.
"""
import logging

logger = logging.getLogger(__name__)

FONT = 'Times New Roman'


def collect_purchase_order_variables(po, company):
    """Everything the purchase-order template can refer to.

    Flat names, the same shape the sales collectors use, because an
    administrator editing the template reads these names and nothing else
    explains them.
    """
    def money(value):
        # Formatted here rather than through a shared helper: I reached for
        # `app.services.money.format_money` and it does not exist. The same
        # `{:,.0f}` shape the existing PO builder uses is the honest thing to
        # copy, since this template must render identically to it.
        return f'{float(value or 0):,.0f}'

    supplier = po.supplier
    return {
        'company_name': getattr(company, 'name', '') or '',
        'company_address': getattr(company, 'address', '') or '',
        'company_phone': getattr(company, 'phone', '') or '',
        'company_tax_code': getattr(company, 'tax_code', '') or '',

        'po_number': po.po_number or '',
        'order_date': po.order_date.strftime('%d/%m/%Y') if po.order_date else '',
        'expected_date': (po.expected_date.strftime('%d/%m/%Y')
                          if po.expected_date else ''),

        'supplier_name': (supplier.name if supplier else '(chưa chọn)'),
        'supplier_address': (supplier.address or '') if supplier else '',
        'supplier_contact': (supplier.contact_person or '') if supplier else '',
        'supplier_phone': (supplier.phone or '') if supplier else '',

        'store_name': getattr(po.store, 'name', '') if po.store else '',
        'notes': po.notes or '',

        'subtotal': money(po.subtotal),
        'vat_rate': f'{float(po.vat_rate or 0):g}',
        'vat_amount': money(po.vat_amount),
        'total_amount': money(po.total_amount),

        'lines': [{
            'index': index,
            'material_code': (line.material.material_code
                              if line.material else ''),
            'material_name': (line.material.name if line.material
                              else str(line.material_id)),
            'unit': line.unit or '',
            'quantity': f'{float(line.quantity_ordered or 0):g}',
            'unit_price': money(line.unit_price),
            'line_total': money(line.line_total),
        } for index, line in enumerate(po.lines, 1)],
    }


def build_default_purchase_order_template(path):
    """Write the current PO layout out as an editable .docx template.

    Mirrors `build_purchase_order_docx` field for field. Kept beside it rather
    than inside it so the builder stays the thing that renders TODAY's
    documents while this one only ever produces a starting template.
    """
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt

    CENTER = WD_ALIGN_PARAGRAPH.CENTER
    RIGHT = WD_ALIGN_PARAGRAPH.RIGHT

    doc = Document()
    doc.styles['Normal'].font.name = FONT
    doc.styles['Normal'].font.size = Pt(11)

    def para(text, size=11, bold=False, italic=False, align=None):
        paragraph = doc.add_paragraph()
        if align is not None:
            paragraph.alignment = align
        run = paragraph.add_run(text)
        run.font.name = FONT
        run.font.size = Pt(size)
        run.bold = bold
        run.italic = italic
        return paragraph

    para('{{ company_name }}', size=12, bold=True, align=CENTER)
    para('Địa chỉ: {{ company_address }}', size=9, align=CENTER)
    para('ĐT: {{ company_phone }}   -   MST: {{ company_tax_code }}',
         size=9, align=CENTER)

    para('ĐƠN ĐẶT HÀNG', size=16, bold=True, align=CENTER)
    para('Số: {{ po_number }}', bold=True, align=CENTER)
    para('Ngày: {{ order_date }}', size=10, italic=True, align=CENTER)

    para('Kính gửi Nhà cung cấp: {{ supplier_name }}', bold=True)
    para('Địa chỉ: {{ supplier_address }}', size=10)
    para('Người liên hệ: {{ supplier_contact }}   -   ĐT: {{ supplier_phone }}',
         size=10)

    para('Đề nghị Quý nhà cung cấp cung cấp các mặt hàng sau:')

    headers = ['STT', 'Mã VT', 'Tên vật tư', 'ĐVT', 'SL đặt', 'Đơn giá',
               'Thành tiền']
    table = doc.add_table(rows=4, cols=len(headers))
    table.style = 'Table Grid'
    for index, heading in enumerate(headers):
        cell = table.rows[0].cells[index]
        cell.text = ''
        run = cell.paragraphs[0].add_run(heading)
        run.bold = True
        run.font.name = FONT
        cell.paragraphs[0].alignment = CENTER

    # THE LOOP TAGS GO IN THEIR OWN ROWS, above and below the row that
    # repeats. Not both in the repeating row, which is what the engine's
    # docstring used to say and what every docxtpl example shows.
    #
    # Measured: `DocxTemplate.patch_xml` replaces an entire `<w:tr>` that
    # contains a `{%tr %}` tag with just that tag. Put `for` and `endfor` in
    # the SAME row and that row — data cells and all — is replaced by one of
    # them, and rendering dies with "Encountered unknown tag 'endfor'".
    #
    # docxtpl 0.20.2. The tag rows disappear on render, so the output has the
    # header row followed by one row per line, which is the intended result.
    table.rows[1].cells[0].text = '{%tr for ln in lines %}'
    body = table.rows[2].cells
    body[0].text = '{{ ln.index }}'
    body[1].text = '{{ ln.material_code }}'
    body[2].text = '{{ ln.material_name }}'
    body[3].text = '{{ ln.unit }}'
    body[4].text = '{{ ln.quantity }}'
    body[5].text = '{{ ln.unit_price }}'
    body[6].text = '{{ ln.line_total }}'
    table.rows[3].cells[0].text = '{%tr endfor %}'

    para('Cộng tiền hàng: {{ subtotal }} đ', align=RIGHT)
    para('VAT ({{ vat_rate }}%): {{ vat_amount }} đ', align=RIGHT)
    para('TỔNG CỘNG: {{ total_amount }} đ', bold=True, align=RIGHT)

    para('Ngày giao hàng dự kiến: {{ expected_date }}')
    para('Giao đến kho: {{ store_name }}')
    para('Ghi chú: {{ notes }}')

    signatures = doc.add_table(rows=1, cols=2)
    for cell, title in ((signatures.rows[0].cells[0], 'NHÀ CUNG CẤP'),
                        (signatures.rows[0].cells[1], 'ĐẠI DIỆN BÊN MUA')):
        cell.text = ''
        run = cell.paragraphs[0].add_run(title)
        run.bold = True
        run.font.name = FONT
        cell.paragraphs[0].alignment = CENTER
        note = cell.add_paragraph()
        note.alignment = CENTER
        note_run = note.add_run('(Ký, ghi rõ họ tên)')
        note_run.font.name = FONT
        note_run.font.size = Pt(9)
        note_run.italic = True

    doc.save(path)
    return path
