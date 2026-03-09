"""
create_docx_templates.py
========================
Generates four Vietnamese .docx template files for sofa-flow:
  - quotation_template.docx   (Bao Gia)
  - contract_template.docx    (Hop Dong)
  - handover_template.docx    (Bien Ban Ban Giao)
  - payment_template.docx     (De Nghi Thanh Toan)

All templates use docxtpl / Jinja2 syntax:
  - {{ variable }}             scalar substitution
  - {%tr for item in items %}  repeat table row (placed in first cell of row)
  - {%tr endfor %}             end table row loop (placed in last cell of row)
"""

import os
from docx import Document
from docx.shared import Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'app', 'uploads', 'templates')
os.makedirs(OUTPUT_DIR, exist_ok=True)

LIGHT_BLUE  = '2E74B5'
HEADER_TEXT = (255, 255, 255)
TOTAL_BG    = 'D9E1F2'
SUBTOTAL_BG = 'EEF3FB'


def _set_font(run, name='Times New Roman', size=11, bold=False,
              italic=False, color=None):
    run.font.name = name
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    if color:
        run.font.color.rgb = RGBColor(*color)


def _para(doc, text='', align=WD_ALIGN_PARAGRAPH.LEFT,
          bold=False, size=11, space_before=0, space_after=4, italic=False):
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after  = Pt(space_after)
    if text:
        run = p.add_run(text)
        _set_font(run, bold=bold, size=size, italic=italic)
    return p


def _set_cell_bg(cell, hex_color):
    tc   = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd  = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), hex_color)
    tcPr.append(shd)


def _set_cell_text(cell, text, bold=False, size=10,
                   align=WD_ALIGN_PARAGRAPH.LEFT, color=None, italic=False):
    cell.text = ''
    p = cell.paragraphs[0]
    p.alignment = align
    run = p.add_run(text)
    _set_font(run, bold=bold, size=size, color=color, italic=italic)


def _set_table_borders(table):
    tbl   = table._tbl
    tblPr = tbl.tblPr
    if tblPr is None:
        tblPr = OxmlElement('w:tblPr')
        tbl.insert(0, tblPr)
    borders = OxmlElement('w:tblBorders')
    for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        el = OxmlElement(f'w:{side}')
        el.set(qn('w:val'), 'single')
        el.set(qn('w:sz'), '4')
        el.set(qn('w:space'), '0')
        el.set(qn('w:color'), 'AAAAAA')
        borders.append(el)
    tblPr.append(borders)


def _add_header_row(table, headers, bg=LIGHT_BLUE, text_color=HEADER_TEXT):
    row = table.add_row()
    for i, hdr in enumerate(headers):
        cell = row.cells[i]
        _set_cell_bg(cell, bg)
        _set_cell_text(cell, hdr, bold=True, size=9,
                       align=WD_ALIGN_PARAGRAPH.CENTER, color=text_color)
    return row


def _col_widths(table, widths_cm):
    for i, col in enumerate(table.columns):
        if i < len(widths_cm):
            for cell in col.cells:
                cell.width = Cm(widths_cm[i])


def _hr(doc):
    p = doc.add_paragraph()
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), '8')
    bottom.set(qn('w:space'), '1')
    bottom.set(qn('w:color'), '2E74B5')
    pBdr.append(bottom)
    pBdr.insert(0, bottom)
    p.paragraph_format.space_after = Pt(3)
    return p


def _company_header(doc):
    _para(doc, '{{ company_name }}', bold=True, size=13,
          align=WD_ALIGN_PARAGRAPH.CENTER, space_after=1)
    _para(doc, 'Tru so: {{ company_address }}', size=9,
          align=WD_ALIGN_PARAGRAPH.CENTER, space_after=1)
    _para(doc, 'San xuat: {{ company_production_address }}', size=9,
          align=WD_ALIGN_PARAGRAPH.CENTER, space_after=1)
    _para(doc, 'DT: {{ company_phone }}  |  Email: {{ company_email }}  |  MST: {{ company_tax_code }}',
          size=9, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
    _hr(doc)


def _info_table(doc, rows_data, widths_cm=None):
    tbl = doc.add_table(rows=len(rows_data), cols=4)
    for r, (l1, v1, l2, v2) in enumerate(rows_data):
        row = tbl.rows[r]
        _set_cell_text(row.cells[0], l1, bold=True, size=9)
        _set_cell_text(row.cells[1], v1, size=9)
        _set_cell_text(row.cells[2], l2, bold=bool(l2), size=9)
        _set_cell_text(row.cells[3], v2, size=9)
    if widths_cm:
        _col_widths(tbl, widths_cm)
    return tbl


def _add_items_table(doc, col_headers, data_values, col_widths_cm):
    tbl = doc.add_table(rows=0, cols=len(col_headers))
    _set_table_borders(tbl)
    _add_header_row(tbl, col_headers)

    open_row = tbl.add_row()
    _set_cell_text(open_row.cells[0], '{%tr for item in items %}', size=1)
    for i in range(1, len(col_headers)):
        _set_cell_text(open_row.cells[i], '', size=1)

    data_row = tbl.add_row()
    for i, val in enumerate(data_values):
        align = (WD_ALIGN_PARAGRAPH.CENTER if i in (0, 2, 3) else
                 WD_ALIGN_PARAGRAPH.RIGHT  if i in (4, 5) else
                 WD_ALIGN_PARAGRAPH.LEFT)
        _set_cell_text(data_row.cells[i], val, size=9, align=align)

    close_row = tbl.add_row()
    _set_cell_text(close_row.cells[0], '{%tr endfor %}', size=1)
    for i in range(1, len(col_headers)):
        _set_cell_text(close_row.cells[i], '', size=1)

    _col_widths(tbl, col_widths_cm)
    return tbl


def _add_vat_subtotals(doc, col_count, merge_to_col, col_widths_cm):
    tbl = doc.add_table(rows=3, cols=col_count)
    _set_table_borders(tbl)
    amount_col = col_count - 1

    rows_cfg = [
        ('Cong tien hang:', '{{ subtotal }}',     SUBTOTAL_BG, False),
        ('Thue VAT {{ vat_rate }}%:', '{{ vat_amount }}', SUBTOTAL_BG, False),
        ('TONG CONG:',       '{{ total_amount }}', TOTAL_BG,    True),
    ]
    for r, (label, value, bg, bold) in enumerate(rows_cfg):
        row = tbl.rows[r]
        row.cells[0].merge(row.cells[merge_to_col])
        _set_cell_bg(row.cells[0], bg)
        _set_cell_text(row.cells[0], label, bold=True, size=9,
                       align=WD_ALIGN_PARAGRAPH.RIGHT)
        _set_cell_bg(row.cells[amount_col], bg)
        _set_cell_text(row.cells[amount_col], value, bold=bold, size=9,
                       align=WD_ALIGN_PARAGRAPH.RIGHT)
        for i in range(merge_to_col + 1, amount_col):
            _set_cell_bg(row.cells[i], bg)
            _set_cell_text(row.cells[i], '', size=9)

    _col_widths(tbl, col_widths_cm)
    return tbl


def _signature_block(doc, left_title, left_name_tpl, right_title, right_name_tpl):
    _para(doc, '', space_before=8, space_after=2)
    tbl = doc.add_table(rows=1, cols=2)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER

    def _fill_sig(cell, title_text, name_tpl):
        cell.text = ''
        for line in title_text.split('\n'):
            p = cell.add_paragraph(line)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in p.runs:
                _set_font(run, bold=True, size=10)
        for _ in range(4):
            p = cell.add_paragraph('')
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p = cell.add_paragraph(name_tpl)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in p.runs:
            _set_font(run, bold=True, italic=True, size=10)

    _fill_sig(tbl.cell(0, 0), left_title,  left_name_tpl)
    _fill_sig(tbl.cell(0, 1), right_title, right_name_tpl)


# ===========================================================================
# Template 1: Bao Gia (Quotation)
# ===========================================================================

def create_quotation_template():
    doc = Document()
    for section in doc.sections:
        section.top_margin    = Cm(1.8)
        section.bottom_margin = Cm(1.8)
        section.left_margin   = Cm(2.5)
        section.right_margin  = Cm(2.0)

    _company_header(doc)
    _para(doc, 'BAO GIA', bold=True, size=18,
          align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
    _para(doc, 'So: {{ quotation_number }}', bold=False, size=11,
          align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
    _para(doc, '{{ city }}, ngay {{ quotation_date }}', italic=True, size=10,
          align=WD_ALIGN_PARAGRAPH.RIGHT, space_after=8)

    _para(doc, 'BEN MUA (KHACH HANG):', bold=True, size=10, space_after=2)
    _info_table(doc, [
        ('Ten cong ty:', '{{ customer_name }}',    'Ma KH:', '{{ customer_code }}'),
        ('MST:',        '{{ customer_tax_code }}', 'Dien thoai:', '{{ customer_phone }}'),
        ('Dia chi:',    '{{ customer_address }}',  'Email:', '{{ customer_email }}'),
        ('Nguoi dai dien:', '{{ customer_representative }}', 'Chuc vu:', '{{ customer_representative_title }}'),
    ], widths_cm=[3.4, 5.0, 3.0, 5.2])
    _para(doc, '', space_before=4, space_after=2)

    _para(doc, 'BEN BAN (CONG TY):', bold=True, size=10, space_after=2)
    _info_table(doc, [
        ('Ten cong ty:', '{{ company_name }}',  'MST:', '{{ company_tax_code }}'),
        ('Dia chi:',    '{{ company_address }}', 'Dien thoai:', '{{ company_phone }}'),
        ('Nguoi dai dien:', '{{ company_representative_name }}', 'Chuc vu:', '{{ company_representative_title }}'),
    ], widths_cm=[3.4, 5.0, 3.0, 5.2])
    _para(doc, '', space_before=6, space_after=2)

    _para(doc, 'BANG GIA SAN PHAM / DICH VU:', bold=True, size=10, space_after=4)
    col_headers = ['STT', 'Ten hang hoa / Cong viec', 'DVT', 'So luong', 'Don gia (VND)', 'Thanh tien (VND)']
    data_values = ['{{ item.stt }}', '{{ item.name }}', '{{ item.unit }}',
                   '{{ item.quantity }}', '{{ item.unit_price }}', '{{ item.total }}']
    widths_cm   = [1.0, 6.5, 1.3, 1.5, 2.8, 3.1]
    _add_items_table(doc, col_headers, data_values, widths_cm)
    _add_vat_subtotals(doc, col_count=6, merge_to_col=4, col_widths_cm=widths_cm)
    _para(doc, '', space_before=4, space_after=2)

    _para(doc, 'DIEU KHOAN THANH TOAN:', bold=True, size=10, space_after=2)
    _para(doc, '{{ payment_terms }}', size=10, space_after=4)

    _para(doc, 'THONG TIN NGAN HANG:', bold=True, size=10, space_after=2)
    _para(doc, '- Ngan hang: {{ company_bank_name }}', size=10, space_after=1)
    _para(doc, '- So tai khoan: {{ company_bank_account_number }}', size=10, space_after=1)
    _para(doc, '- Chu tai khoan: {{ company_bank_account_holder }}', size=10, space_after=4)
    _para(doc, 'Ghi chu: {{ notes }}', size=10, italic=True, space_after=10)

    _signature_block(doc,
        left_title='DAI DIEN KHACH HANG\n(Ky, ghi ro ho ten)',
        left_name_tpl='{{ customer_representative }}',
        right_title='DAI DIEN CONG TY\n{{ company_representative_title }}\n(Ky, ghi ro ho ten)',
        right_name_tpl='{{ company_representative_name }}',
    )

    path = os.path.join(OUTPUT_DIR, 'quotation_template.docx')
    doc.save(path)
    print(f'  Created: {path}')
    return path


# ===========================================================================
# Template 2: Hop Dong (Contract)
# ===========================================================================

def create_contract_template():
    doc = Document()
    for section in doc.sections:
        section.top_margin    = Cm(1.8)
        section.bottom_margin = Cm(1.8)
        section.left_margin   = Cm(2.5)
        section.right_margin  = Cm(2.0)

    _company_header(doc)
    _para(doc, 'HOP DONG MUA BAN', bold=True, size=18,
          align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
    _para(doc, 'So: {{ contract_number }}', bold=False, size=11,
          align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
    _para(doc, 'Can cu vao Bao gia so {{ quotation_number }}', italic=True, size=10,
          align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
    _para(doc, '{{ city }}, ngay {{ contract_date }}', italic=True, size=10,
          align=WD_ALIGN_PARAGRAPH.RIGHT, space_after=8)

    _para(doc, 'BEN MUA (A):', bold=True, size=10, space_after=2)
    _info_table(doc, [
        ('Ten cong ty:', '{{ customer_name }}',    'Ma KH:', '{{ customer_code }}'),
        ('MST:',        '{{ customer_tax_code }}', 'Dien thoai:', '{{ customer_phone }}'),
        ('Dia chi:',    '{{ customer_address }}',  'Email:', '{{ customer_email }}'),
        ('Nguoi dai dien:', '{{ customer_representative }}', 'Chuc vu:', '{{ customer_representative_title }}'),
    ], widths_cm=[3.4, 5.0, 3.0, 5.2])
    _para(doc, '', space_before=4, space_after=2)

    _para(doc, 'BEN BAN (B):', bold=True, size=10, space_after=2)
    _info_table(doc, [
        ('Ten cong ty:', '{{ company_name }}',  'MST:', '{{ company_tax_code }}'),
        ('Dia chi:',    '{{ company_address }}', 'Dien thoai:', '{{ company_phone }}'),
        ('Nguoi dai dien:', '{{ company_representative_name }}', 'Chuc vu:', '{{ company_representative_title }}'),
    ], widths_cm=[3.4, 5.0, 3.0, 5.2])
    _para(doc, '', space_before=6, space_after=2)

    _para(doc, 'DIEU 1: HANG HOA / DICH VU', bold=True, size=10, space_after=4)
    col_headers = ['STT', 'Ten hang hoa / Cong viec', 'DVT', 'So luong', 'Don gia (VND)', 'Thanh tien (VND)']
    data_values = ['{{ item.stt }}', '{{ item.name }}', '{{ item.unit }}',
                   '{{ item.quantity }}', '{{ item.unit_price }}', '{{ item.total }}']
    widths_cm   = [1.0, 6.5, 1.3, 1.5, 2.8, 3.1]
    _add_items_table(doc, col_headers, data_values, widths_cm)
    _add_vat_subtotals(doc, col_count=6, merge_to_col=4, col_widths_cm=widths_cm)
    _para(doc, '', space_before=6, space_after=2)

    _para(doc, 'DIEU 2: THANH TOAN', bold=True, size=10, space_after=2)
    adv_tbl = doc.add_table(rows=3, cols=2)
    _set_table_borders(adv_tbl)
    for r, (l, v) in enumerate([
        ('Tam ung {{ advance_percentage }}%:', '{{ advance_amount }} VND'),
        ('So tien con lai:', '{{ contract_value }} - {{ advance_amount }} VND'),
        ('Hinh thuc:', 'Chuyen khoan'),
    ]):
        _set_cell_text(adv_tbl.rows[r].cells[0], l, bold=True, size=9)
        _set_cell_text(adv_tbl.rows[r].cells[1], v, size=9)
    _col_widths(adv_tbl, [5.0, 11.6])
    _para(doc, '', space_before=6, space_after=2)

    _para(doc, 'DIEU 3: DIEU KHOAN CHUNG', bold=True, size=10, space_after=2)
    _para(doc, '{{ terms_and_conditions }}', size=10, space_after=6)
    _para(doc, 'Ghi chu: {{ notes }}', size=10, italic=True, space_after=10)

    _signature_block(doc,
        left_title='DAI DIEN BEN MUA (A)\n{{ customer_representative_title }}\n(Ky, ghi ro ho ten)',
        left_name_tpl='{{ customer_representative }}',
        right_title='DAI DIEN BEN BAN (B)\n{{ company_representative_title }}\n(Ky, ghi ro ho ten)',
        right_name_tpl='{{ company_representative_name }}',
    )

    path = os.path.join(OUTPUT_DIR, 'contract_template.docx')
    doc.save(path)
    print(f'  Created: {path}')
    return path


# ===========================================================================
# Template 3: Bien Ban Ban Giao (Handover Record)
# ===========================================================================

def create_handover_template():
    doc = Document()
    for section in doc.sections:
        section.top_margin    = Cm(1.8)
        section.bottom_margin = Cm(1.8)
        section.left_margin   = Cm(2.5)
        section.right_margin  = Cm(2.0)

    _company_header(doc)
    _para(doc, 'BIEN BAN BAN GIAO', bold=True, size=18,
          align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
    _para(doc, 'So: {{ report_number }}', bold=False, size=11,
          align=WD_ALIGN_PARAGRAPH.CENTER, space_after=8)

    # Time / location block
    time_tbl = doc.add_table(rows=3, cols=4)
    _set_table_borders(time_tbl)
    for r, (l1, v1, l2, v2) in enumerate([
        ('Ngay ban giao:', '{{ handover_date }}', 'Dia diem:', '{{ handover_location }}'),
        ('Gio bat dau:',  '{{ start_time }}',     'Gio ket thuc:', '{{ end_time }}'),
        ('Don hang:',     '{{ order_code }}',     'Noi dung:', '{{ order_title }}'),
    ]):
        row = time_tbl.rows[r]
        _set_cell_text(row.cells[0], l1, bold=True, size=9)
        _set_cell_text(row.cells[1], v1, size=9)
        _set_cell_text(row.cells[2], l2, bold=True, size=9)
        _set_cell_text(row.cells[3], v2, size=9)
    _col_widths(time_tbl, [3.0, 4.8, 3.0, 5.8])
    _para(doc, '', space_before=6, space_after=2)

    _para(doc, 'BEN GIAO (BEN BAN):', bold=True, size=10, space_after=2)
    _info_table(doc, [
        ('Ten cong ty:', '{{ company_name }}',  'MST:', '{{ company_tax_code }}'),
        ('Dia chi:',    '{{ company_address }}', 'Dien thoai:', '{{ company_phone }}'),
        ('Nguoi dai dien:', '{{ company_representative }}', 'Chuc vu:', '{{ company_representative_title }}'),
    ], widths_cm=[3.4, 5.0, 3.0, 5.2])
    _para(doc, '', space_before=4, space_after=2)

    _para(doc, 'BEN NHAN (BEN MUA):', bold=True, size=10, space_after=2)
    _info_table(doc, [
        ('Ten cong ty:', '{{ customer_name }}',    'Ma KH:', '{{ customer_code }}'),
        ('MST:',        '{{ customer_tax_code }}', 'Dien thoai:', '{{ customer_phone }}'),
        ('Dia chi:',    '{{ customer_address }}',  '', ''),
        ('Nguoi dai dien:', '{{ customer_representative }}', 'Chuc vu:', '{{ customer_representative_title }}'),
    ], widths_cm=[3.4, 5.0, 3.0, 5.2])
    _para(doc, '', space_before=6, space_after=2)

    _para(doc, 'DANH MUC SAN PHAM BAN GIAO:', bold=True, size=10, space_after=4)
    col_headers = ['STT', 'Ten hang hoa', 'DVT', 'SL Giao', 'SL Nhan',
                   'Don gia (VND)', 'Thanh tien (VND)', 'Tinh trang']
    data_values = ['{{ item.stt }}', '{{ item.name }}', '{{ item.unit }}',
                   '{{ item.delivered_qty }}', '{{ item.accepted_qty }}',
                   '{{ item.unit_price }}',    '{{ item.total }}',
                   '{{ item.accepted }}']
    widths_cm   = [0.9, 4.0, 1.0, 1.2, 1.2, 2.5, 2.8, 2.0]
    _add_items_table(doc, col_headers, data_values, widths_cm)
    _add_vat_subtotals(doc, col_count=8, merge_to_col=6, col_widths_cm=widths_cm)
    _para(doc, '', space_before=6, space_after=2)

    _para(doc, 'KET LUAN:', bold=True, size=10, space_after=2)
    _para(doc, '{{ product_condition }}', size=10, space_after=2)
    _para(doc, 'Ghi chu: {{ notes }}', size=10, space_after=4)
    _para(doc, 'Bien ban duoc lap thanh {{ copies_count }} ban, moi ben giu 01 ban, co gia tri phap ly nhu nhau.',
          size=10, italic=True, space_after=10)

    _signature_block(doc,
        left_title='DAI DIEN BEN NHAN\n{{ customer_representative_title }}\n(Ky, ghi ro ho ten)',
        left_name_tpl='{{ customer_representative }}',
        right_title='DAI DIEN BEN GIAO\n{{ company_representative_title }}\n(Ky, ghi ro ho ten)',
        right_name_tpl='{{ company_representative }}',
    )

    path = os.path.join(OUTPUT_DIR, 'handover_template.docx')
    doc.save(path)
    print(f'  Created: {path}')
    return path


# ===========================================================================
# Template 4: De Nghi Thanh Toan (Payment Request)
# ===========================================================================

def create_payment_template():
    doc = Document()
    for section in doc.sections:
        section.top_margin    = Cm(1.8)
        section.bottom_margin = Cm(1.8)
        section.left_margin   = Cm(2.5)
        section.right_margin  = Cm(2.0)

    _company_header(doc)
    _para(doc, 'DE NGHI THANH TOAN', bold=True, size=18,
          align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
    _para(doc, 'So: {{ report_number }}', bold=False, size=11,
          align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
    _para(doc, '{{ payment_type_display }}', bold=False, size=11,
          align=WD_ALIGN_PARAGRAPH.CENTER, space_after=8)

    _para(doc, 'I. CAN CU:', bold=True, size=10, space_after=2)
    _info_table(doc, [
        ('Hop dong / Bao gia so:', '{{ quotation_number }}', 'Ngay lap:', '{{ quotation_reference_date }}'),
        ('Don hang:', '{{ order_code }}', 'Ngay thanh toan:', '{{ payment_date }}'),
    ], widths_cm=[4.0, 5.0, 3.5, 4.1])
    _para(doc, '', space_before=4, space_after=2)

    _para(doc, 'II. BEN YEU CAU THANH TOAN:', bold=True, size=10, space_after=2)
    _info_table(doc, [
        ('Ten cong ty:', '{{ company_name }}',  'MST:', '{{ company_tax_code }}'),
        ('Dia chi:',    '{{ company_address }}', 'Dien thoai:', '{{ company_phone }}'),
        ('Nguoi dai dien:', '{{ company_representative_name }}', 'Chuc vu:', '{{ company_representative_title }}'),
    ], widths_cm=[3.4, 5.0, 3.0, 5.2])
    _para(doc, '', space_before=4, space_after=2)

    _para(doc, 'III. BEN THANH TOAN:', bold=True, size=10, space_after=2)
    _info_table(doc, [
        ('Ten cong ty:', '{{ customer_name }}',    'Ma KH:', '{{ customer_code }}'),
        ('MST:',        '{{ customer_tax_code }}', 'Dien thoai:', '{{ customer_phone }}'),
        ('Dia chi:',    '{{ customer_address }}',  '', ''),
        ('Nguoi dai dien:', '{{ customer_representative }}', 'Chuc vu:', '{{ customer_representative_title }}'),
    ], widths_cm=[3.4, 5.0, 3.0, 5.2])
    _para(doc, '', space_before=6, space_after=2)

    _para(doc, 'IV. GIA TRI THANH TOAN:', bold=True, size=10, space_after=2)
    _para(doc, 'Phan cong viec da hoan thanh: {{ work_completed_summary }}',
          size=10, space_after=4)
    col_headers = ['STT', 'Noi dung cong viec', 'DVT', 'So luong',
                   'Don gia (VND)', 'Thanh tien (VND)']
    data_values = ['{{ item.stt }}', '{{ item.name }}', '{{ item.unit }}',
                   '{{ item.quantity }}', '{{ item.unit_price }}', '{{ item.total }}']
    widths_cm   = [1.0, 6.5, 1.3, 1.5, 2.8, 3.1]
    _add_items_table(doc, col_headers, data_values, widths_cm)
    _add_vat_subtotals(doc, col_count=6, merge_to_col=4, col_widths_cm=widths_cm)
    _para(doc, '', space_before=4, space_after=2)

    _para(doc, 'V. PHAN TICH SO TIEN:', bold=True, size=10, space_after=2)
    adv_tbl = doc.add_table(rows=3, cols=2)
    _set_table_borders(adv_tbl)
    for r, (l, v, bold_row) in enumerate([
        ('Gia tri hop dong (bao gom VAT):', '{{ amount }} VND', False),
        ('Da tam ung {{ advance_percentage }}%:', '{{ advance_amount }} VND', False),
        ('SO TIEN CON LAI CAN THANH TOAN:', '{{ remaining_amount }} VND', True),
    ]):
        _set_cell_text(adv_tbl.rows[r].cells[0], l, bold=bold_row, size=9)
        _set_cell_text(adv_tbl.rows[r].cells[1], v, bold=bold_row, size=9,
                       align=WD_ALIGN_PARAGRAPH.RIGHT)
        if bold_row:
            _set_cell_bg(adv_tbl.rows[r].cells[0], TOTAL_BG)
            _set_cell_bg(adv_tbl.rows[r].cells[1], TOTAL_BG)
    _col_widths(adv_tbl, [10.0, 6.6])
    _para(doc, 'Bang chu: {{ amount_in_words }}', size=10, italic=True, space_before=4, space_after=4)

    _para(doc, 'VI. HINH THUC THANH TOAN:', bold=True, size=10, space_after=2)
    _para(doc, 'Chuyen khoan ngan hang theo thong tin duoi day:', size=10, space_after=2)
    _para(doc, '- Ngan hang: {{ company_bank_name }}', size=10, space_after=1)
    _para(doc, '- So tai khoan: {{ company_bank_account_number }}', size=10, space_after=1)
    _para(doc, '- Ten tai khoan: {{ company_bank_account_holder }}', size=10, space_after=4)
    _para(doc, 'Ghi chu: {{ notes }}', size=10, italic=True, space_after=10)

    _signature_block(doc,
        left_title='DAI DIEN BEN THANH TOAN\n{{ customer_representative_title }}\n(Ky, ghi ro ho ten)',
        left_name_tpl='{{ customer_representative }}',
        right_title='DAI DIEN BEN YEU CAU\n{{ company_representative_title }}\n(Ky, ghi ro ho ten)',
        right_name_tpl='{{ company_representative_name }}',
    )

    path = os.path.join(OUTPUT_DIR, 'payment_template.docx')
    doc.save(path)
    print(f'  Created: {path}')
    return path


# ===========================================================================
# Main
# ===========================================================================

if __name__ == '__main__':
    print('Generating DOCX templates ...')
    print(f'Output: {OUTPUT_DIR}\n')
    create_quotation_template()
    create_contract_template()
    create_handover_template()
    create_payment_template()
    print('\nDone. To seed into DB, run:')
    print('  python seed_docx_templates.py')
