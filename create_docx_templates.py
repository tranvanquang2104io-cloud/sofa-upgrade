"""
create_docx_templates.py
========================
Generates four .docx template files for the sofa-flow application:
  - quotation_template.docx
  - contract_template.docx
  - handover_template.docx
  - payment_template.docx

All templates use docxtpl / Jinja2 syntax:
  • {{ variable }}            – scalar substitution
  • {%tr for item in items %} – repeat table row (placed in first cell of row)
  • {%tr endfor %}            – end table row loop (placed in last cell of same row)

Run once to create the files, then upload/replace with your polished Word version.
After replacing, re-run `seed_docx_templates.py` to update the DB record.
"""

import os
from docx import Document
from docx.shared import Pt, RGBColor, Cm, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'app', 'uploads', 'templates')
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ===========================================================================
# Helper utilities
# ===========================================================================

def _set_font(run, name='Times New Roman', size=11, bold=False,
              italic=False, color: tuple = None):
    run.font.name = name
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    if color:
        run.font.color.rgb = RGBColor(*color)


def _para(doc, text='', align=WD_ALIGN_PARAGRAPH.LEFT,
          bold=False, size=11, space_before=0, space_after=6):
    p = doc.add_paragraph()
    p.alignment = align
    pf = p.paragraph_format
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(space_after)
    if text:
        run = p.add_run(text)
        _set_font(run, bold=bold, size=size)
    return p


def _set_cell_bg(cell, hex_color: str):
    """Set cell background shading (e.g. '4472C4' for blue)."""
    tc    = cell._tc
    tcPr  = tc.get_or_add_tcPr()
    shd   = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), hex_color)
    tcPr.append(shd)


def _set_cell_text(cell, text, bold=False, size=10,
                   align=WD_ALIGN_PARAGRAPH.LEFT,
                   color: tuple = None):
    cell.text = ''
    p = cell.paragraphs[0]
    p.alignment = align
    run = p.add_run(text)
    _set_font(run, bold=bold, size=size, color=color)


def _set_table_borders(table):
    """Add thin borders to every cell in a table."""
    tbl  = table._tbl
    tblPr = tbl.tblPr
    if tblPr is None:
        tblPr = OxmlElement('w:tblPr')
        tbl.insert(0, tblPr)
    tblBorders = OxmlElement('w:tblBorders')
    for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        el = OxmlElement(f'w:{side}')
        el.set(qn('w:val'), 'single')
        el.set(qn('w:sz'), '4')
        el.set(qn('w:space'), '0')
        el.set(qn('w:color'), '000000')
        tblBorders.append(el)
    tblPr.append(tblBorders)


def _add_header_row(table, headers: list, bg='2E74B5', text_color=(255, 255, 255)):
    """Add a styled header row to the table."""
    row = table.add_row()
    for i, hdr in enumerate(headers):
        cell = row.cells[i]
        _set_cell_bg(cell, bg)
        _set_cell_text(cell, hdr, bold=True, size=10,
                       align=WD_ALIGN_PARAGRAPH.CENTER, color=text_color)
    return row


def _col_widths(table, widths_cm: list):
    """Set column widths in cm."""
    for i, col in enumerate(table.columns):
        if i < len(widths_cm):
            for cell in col.cells:
                cell.width = Cm(widths_cm[i])


def _hr(doc):
    """Thin horizontal rule paragraph."""
    p = doc.add_paragraph()
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), '6')
    bottom.set(qn('w:space'), '1')
    bottom.set(qn('w:color'), 'AAAAAA')
    pBdr.append(bottom)
    pPr.append(pBdr)
    p.paragraph_format.space_after = Pt(4)
    return p


def _company_header(doc):
    """Shared company header block."""
    p = _para(doc, '{{ company_name }}', bold=True, size=13, space_after=2)
    _para(doc, '{{ company_address }}', size=10, space_after=2)
    _para(doc, 'Tel: {{ company_phone }}   |   Email: {{ company_email }}', size=10, space_after=4)
    _hr(doc)


def _add_items_table(doc, cols, data_values, col_widths_cm, total_row_values=None):
    """
    Build a table that repeats rows using docxtpl `{%tr for item in items %}`.

    Structure:
      • Header row (styled)
      • Loop-open row  : only  {%tr for item in items %}  in first cell   ← replaced by {% for item in items %}
      • Data row       : {{ item.xxx }} per cell                           ← repeated by Jinja2 for each item
      • Loop-close row : only  {%tr endfor %}  in first cell              ← replaced by {% endfor %}
      • (Optional) total row

    docxtpl's patch_xml() replaces each entire <w:tr> containing {%tr ...%}
    with the corresponding Jinja2 tag, leaving only the data row to be looped.
    """
    tbl = doc.add_table(rows=0, cols=len(cols))
    _set_table_borders(tbl)
    _add_header_row(tbl, cols)

    # --- loop-open row ---------------------------------------------------
    for_row = tbl.add_row()
    _set_cell_text(for_row.cells[0], '{%tr for item in items %}', size=1)
    for i in range(1, len(cols)):
        _set_cell_text(for_row.cells[i], '', size=1)

    # --- data row --------------------------------------------------------
    data_row = tbl.add_row()
    for i, val in enumerate(data_values):
        align = (WD_ALIGN_PARAGRAPH.CENTER
                 if i in (0, 2, 3, 4, 5) else WD_ALIGN_PARAGRAPH.LEFT)
        _set_cell_text(data_row.cells[i], val, size=9, align=align)

    # --- loop-close row --------------------------------------------------
    end_row = tbl.add_row()
    _set_cell_text(end_row.cells[0], '{%tr endfor %}', size=1)
    for i in range(1, len(cols)):
        _set_cell_text(end_row.cells[i], '', size=1)

    # --- optional total row ---------------------------------------------
    if total_row_values:
        tot_row = tbl.add_row()
        merge_end = total_row_values.get('merge_end', len(cols) - 3)
        amount_col = total_row_values.get('amount_col', len(cols) - 2)
        tot_row.cells[0].merge(tot_row.cells[merge_end])
        _set_cell_text(tot_row.cells[0], total_row_values['label'],
                       bold=True, align=WD_ALIGN_PARAGRAPH.RIGHT, size=10)
        _set_cell_bg(tot_row.cells[amount_col], 'FFF2CC')
        _set_cell_text(tot_row.cells[amount_col], total_row_values['value'],
                       bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, size=10)
        for i in range(amount_col + 1, len(cols)):
            _set_cell_text(tot_row.cells[i], '', size=9)

    _col_widths(tbl, col_widths_cm)
    return tbl


def _signature_table(doc, left_label='DAI DIEN CONG TY\n(Company Representative)',
                     right_label='DAI DIEN KHACH HANG\n(Customer Representative)'):
    """Two-column signature block."""
    _para(doc, space_before=12, space_after=4)
    tbl = doc.add_table(rows=1, cols=2)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    lc = tbl.cell(0, 0)
    rc = tbl.cell(0, 1)
    _set_cell_text(lc, left_label, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, size=10)
    _set_cell_text(rc, right_label, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, size=10)
    # Spacer rows
    for i in range(4):
        row = tbl.add_row()
        _set_cell_text(row.cells[0], '')
        _set_cell_text(row.cells[1], '')
    # Signature name row
    sign_row = tbl.add_row()
    _set_cell_text(sign_row.cells[0], '{{ company_representative }}',
                   bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    _set_cell_text(sign_row.cells[1], '{{ customer_representative }}',
                   bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)


# ===========================================================================
# Template 1: Quotation / Báo Giá
# ===========================================================================

def create_quotation_template():
    doc = Document()

    # Page margins
    for section in doc.sections:
        section.top_margin    = Cm(2.0)
        section.bottom_margin = Cm(2.0)
        section.left_margin   = Cm(2.5)
        section.right_margin  = Cm(2.0)

    _company_header(doc)

    # Title
    _para(doc, 'BÁO GIÁ', bold=True, size=18,
          align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
    _para(doc, '(QUOTATION)', bold=False, size=12,
          align=WD_ALIGN_PARAGRAPH.CENTER, space_after=8)

    # Info table
    info = doc.add_table(rows=5, cols=4)
    _set_table_borders(info)
    data = [
        ('Số BG / No.', '{{ quotation_number }}',
         'Ngày / Date',   '{{ quotation_date }}'),
        ('Hiệu lực / Validity', '{{ validity_days }} ngày',
         'Ngày xuất / Generated', '{{ generated_date }}'),
        ('Mã KH / Customer Code', '{{ customer_code }}',
         'Đơn hàng / Order', '{{ order_code }}'),
        ('Khách hàng / Customer', '{{ customer_name }}',
         'Điện thoại / Phone', '{{ customer_phone }}'),
        ('Địa chỉ / Address', '{{ customer_address }}',
         'Email', '{{ customer_email }}'),
    ]
    for r, (l1, v1, l2, v2) in enumerate(data):
        row = info.rows[r]
        _set_cell_text(row.cells[0], l1, bold=True, size=9)
        _set_cell_text(row.cells[1], v1, size=9)
        _set_cell_text(row.cells[2], l2, bold=True, size=9)
        _set_cell_text(row.cells[3], v2, size=9)
    _col_widths(info, [3.8, 4.5, 3.8, 4.5])
    _para(doc, space_before=8, space_after=4)

    # Heading
    _para(doc, 'DANH MỤC SẢN PHẨM / PRODUCT LIST',
          bold=True, size=11, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)

    # Items table (uses separate for/endfor helper rows for docxtpl)
    cols = ['STT', 'Ten san pham / Product Name', 'DVT', 'SL', 'Don gia (VND)', 'Thanh tien (VND)', 'Ghi chu']
    _add_items_table(
        doc, cols,
        data_values=[
            '{{ item.stt }}', '{{ item.name }}', '{{ item.unit }}',
            '{{ item.quantity }}', '{{ item.unit_price }}', '{{ item.total }}',
            '{{ item.notes }}',
        ],
        col_widths_cm=[1.0, 5.5, 1.2, 1.2, 2.5, 2.5, 2.7],
        total_row_values={
            'label': 'TONG CONG / TOTAL',
            'value': '{{ total_amount }}',
            'merge_end': 4,
            'amount_col': 5,
        },
    )

    _para(doc, space_before=8, space_after=2)

    # Notes
    _para(doc, 'Ghi chú / Notes:', bold=True, size=10)
    _para(doc, '{{ notes }}', size=10, space_after=12)

    _signature_table(doc)

    path = os.path.join(OUTPUT_DIR, 'quotation_template.docx')
    doc.save(path)
    print(f'  ✓ Created: {path}')
    return path


# ===========================================================================
# Template 2: Contract / Hợp Đồng
# ===========================================================================

def create_contract_template():
    doc = Document()

    for section in doc.sections:
        section.top_margin    = Cm(2.0)
        section.bottom_margin = Cm(2.0)
        section.left_margin   = Cm(2.5)
        section.right_margin  = Cm(2.0)

    _company_header(doc)

    _para(doc, 'HỢP ĐỒNG MUA BÁN', bold=True, size=18,
          align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
    _para(doc, '(SALES CONTRACT)', bold=False, size=12,
          align=WD_ALIGN_PARAGRAPH.CENTER, space_after=8)

    info = doc.add_table(rows=6, cols=4)
    _set_table_borders(info)
    data = [
        ('Số HĐ / Contract No.', '{{ contract_number }}',
         'Ngày / Date',           '{{ contract_date }}'),
        ('Tham chiếu BG / Ref. Quotation', '{{ quotation_number }}',
         'Ngày xuất / Generated',           '{{ generated_date }}'),
        ('Mã KH / Customer Code', '{{ customer_code }}',
         'Đơn hàng / Order',       '{{ order_code }}'),
        ('Khách hàng / Customer', '{{ customer_name }}',
         'Điện thoại / Phone',     '{{ customer_phone }}'),
        ('Địa chỉ / Address', '{{ customer_address }}',
         'Email',                  '{{ customer_email }}'),
        ('Giá trị HĐ / Contract Value (VNĐ)', '{{ contract_value }}',
         '',                        ''),
    ]
    for r, (l1, v1, l2, v2) in enumerate(data):
        row = info.rows[r]
        _set_cell_text(row.cells[0], l1, bold=True, size=9)
        _set_cell_text(row.cells[1], v1, size=9)
        _set_cell_text(row.cells[2], l2, bold=True, size=9)
        _set_cell_text(row.cells[3], v2, size=9)
    _col_widths(info, [3.8, 4.5, 3.8, 4.5])
    _para(doc, space_before=8, space_after=4)

    _para(doc, 'BẢNG SẢN PHẨM / PRODUCT TABLE',
          bold=True, size=11, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)

    cols = ['STT', 'Ten san pham / Product Name', 'DVT', 'SL', 'Don gia (VND)', 'Thanh tien (VND)', 'Ghi chu']
    _add_items_table(
        doc, cols,
        data_values=[
            '{{ item.stt }}', '{{ item.name }}', '{{ item.unit }}',
            '{{ item.quantity }}', '{{ item.unit_price }}', '{{ item.total }}',
            '{{ item.notes }}',
        ],
        col_widths_cm=[1.0, 5.5, 1.2, 1.2, 2.5, 2.5, 2.7],
        total_row_values={
            'label': 'TONG CONG / TOTAL',
            'value': '{{ contract_value }}',
            'merge_end': 4,
            'amount_col': 5,
        },
    )

    _para(doc, space_before=10, space_after=2)
    _para(doc, 'ĐIỀU KHOẢN HỢP ĐỒNG / TERMS AND CONDITIONS', bold=True, size=10)
    _para(doc, '{{ terms_and_conditions }}', size=10, space_after=12)

    _signature_table(doc)

    path = os.path.join(OUTPUT_DIR, 'contract_template.docx')
    doc.save(path)
    print(f'  ✓ Created: {path}')
    return path


# ===========================================================================
# Template 3: Handover Record / Biên Bản Bàn Giao
# ===========================================================================

def create_handover_template():
    doc = Document()

    for section in doc.sections:
        section.top_margin    = Cm(2.0)
        section.bottom_margin = Cm(2.0)
        section.left_margin   = Cm(2.5)
        section.right_margin  = Cm(2.0)

    _company_header(doc)

    _para(doc, 'BIÊN BẢN BÀN GIAO', bold=True, size=18,
          align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
    _para(doc, '(HANDOVER RECORD)', bold=False, size=12,
          align=WD_ALIGN_PARAGRAPH.CENTER, space_after=8)

    info = doc.add_table(rows=5, cols=4)
    _set_table_borders(info)
    data = [
        ('Số BB / Record No.', '{{ report_number }}',
         'Ngày BB / Record Date', '{{ report_date }}'),
        ('Ngày bàn giao / Handover Date', '{{ handover_date }}',
         'Ngày xuất / Generated',          '{{ generated_date }}'),
        ('Đơn hàng / Order', '{{ order_code }}',
         'Nội dung / Subject',  '{{ order_title }}'),
        ('Khách hàng / Customer', '{{ customer_name }}',
         'Điện thoại / Phone',    '{{ customer_phone }}'),
        ('Địa chỉ / Address', '{{ customer_address }}',
         'Mã KH / Code',       '{{ customer_code }}'),
    ]
    for r, (l1, v1, l2, v2) in enumerate(data):
        row = info.rows[r]
        _set_cell_text(row.cells[0], l1, bold=True, size=9)
        _set_cell_text(row.cells[1], v1, size=9)
        _set_cell_text(row.cells[2], l2, bold=True, size=9)
        _set_cell_text(row.cells[3], v2, size=9)
    _col_widths(info, [4.0, 4.3, 3.8, 4.5])
    _para(doc, space_before=8, space_after=4)

    _para(doc, 'DANH MỤC HÀNG BÀN GIAO / HANDOVER ITEM LIST',
          bold=True, size=11, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)

    cols = ['STT', 'Ten san pham', 'DVT', 'SL giao', 'SL nghiem thu', 'Ket qua', 'Ly do tu choi', 'Ghi chu']
    _add_items_table(
        doc, cols,
        data_values=[
            '{{ item.stt }}', '{{ item.name }}', '{{ item.unit }}',
            '{{ item.delivered_qty }}', '{{ item.accepted_qty }}',
            '{{ item.accepted }}', '{{ item.rejection_reason }}',
            '{{ item.notes }}',
        ],
        col_widths_cm=[1.0, 4.5, 1.0, 1.3, 1.5, 1.5, 2.5, 2.0],
    )
    _para(doc, space_before=8, space_after=2)

    _para(doc, 'Tình trạng sản phẩm / Product Condition:', bold=True, size=10)
    _para(doc, '{{ product_condition }}', size=10, space_after=4)
    _para(doc, 'Ghi chú / Notes:', bold=True, size=10)
    _para(doc, '{{ notes }}', size=10, space_after=12)

    _signature_table(doc,
                     left_label='ĐẠI DIỆN CÔNG TY\n(Company Rep.)\n{{ company_representative }}',
                     right_label='ĐẠI DIỆN KHÁCH HÀNG\n(Customer Rep.)\n{{ customer_representative }}')

    path = os.path.join(OUTPUT_DIR, 'handover_template.docx')
    doc.save(path)
    print(f'  ✓ Created: {path}')
    return path


# ===========================================================================
# Template 4: Payment Report / Phiếu Thu / Biên Nhận Thanh Toán
# ===========================================================================

def create_payment_template():
    doc = Document()

    for section in doc.sections:
        section.top_margin    = Cm(2.0)
        section.bottom_margin = Cm(2.0)
        section.left_margin   = Cm(2.5)
        section.right_margin  = Cm(2.0)

    _company_header(doc)

    _para(doc, 'BIÊN NHẬN THANH TOÁN', bold=True, size=18,
          align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
    _para(doc, '(PAYMENT RECEIPT)', bold=False, size=12,
          align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
    _para(doc, '{{ payment_type_display }}', bold=False, size=11,
          align=WD_ALIGN_PARAGRAPH.CENTER, space_after=8)

    info = doc.add_table(rows=7, cols=4)
    _set_table_borders(info)
    data = [
        ('Số phiếu / Receipt No.', '{{ report_number }}',
         'Ngày / Date',             '{{ report_date }}'),
        ('Ngày thanh toán / Payment Date', '{{ payment_date }}',
         'Ngày xuất / Generated',           '{{ generated_date }}'),
        ('Loại TT / Payment Type', '{{ payment_type_display }}',
         '',                        ''),
        ('Mã KH / Customer Code', '{{ customer_code }}',
         'Đơn hàng / Order',       '{{ order_code }}'),
        ('Khách hàng / Customer', '{{ customer_name }}',
         '',                       ''),
        ('Số tiền / Amount (VNĐ)', '{{ amount }}',
         'Phương thức / Method',   '{{ payment_method }}'),
        ('Mã giao dịch / Ref.',   '{{ transaction_reference }}',
         '',                       ''),
    ]
    for r, (l1, v1, l2, v2) in enumerate(data):
        row = info.rows[r]
        _set_cell_text(row.cells[0], l1, bold=True, size=9)
        _set_cell_text(row.cells[1], v1, size=9)
        _set_cell_text(row.cells[2], l2, bold=True, size=9)
        _set_cell_text(row.cells[3], v2, size=9)
    _col_widths(info, [3.8, 4.5, 3.8, 4.5])

    # Highlight amount row
    _set_cell_bg(info.rows[5].cells[1], 'E2EFDA')

    _para(doc, space_before=8, space_after=2)
    _para(doc, 'Ghi chú / Notes:', bold=True, size=10)
    _para(doc, '{{ notes }}', size=10, space_after=12)

    _signature_table(doc,
                     left_label='KẾ TOÁN / ACCOUNTANT\n(Company)',
                     right_label='NGƯỜI NỘP TIỀN / PAYER\n{{ customer_name }}')

    path = os.path.join(OUTPUT_DIR, 'payment_template.docx')
    doc.save(path)
    print(f'  ✓ Created: {path}')
    return path


# ===========================================================================
# Main
# ===========================================================================

if __name__ == '__main__':
    print('Creating DOCX templates …')
    print(f'Output directory: {OUTPUT_DIR}\n')
    create_quotation_template()
    create_contract_template()
    create_handover_template()
    create_payment_template()
    print('\nDone.  Edit the .docx files in Word to match your brand, then run:')
    print('  python seed_docx_templates.py')
