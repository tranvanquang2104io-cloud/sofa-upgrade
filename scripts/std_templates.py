# -*- coding: utf-8 -*-
"""Chuẩn hóa mẫu in ấn SofaFlow về MỘT style thống nhất (lấy chuẩn từ Báo giá).

Thống nhất: font Times New Roman, cỡ thân 13pt / tiêu đề 16pt; khối header 2 cột
(thông tin công ty | quốc hiệu-tiêu ngữ-ngày tháng); bảng hạng mục header nền xanh
#2E74B5 chữ trắng; PHẦN CỘNG/TRỪ NẰM TRONG BẢNG ở các hàng in đậm cuối cùng, kết
thúc bằng một con số tổng (nền #D9E1F2); khối chân ký 2 cột.

- Dựng lại 3 mẫu: bàn giao, tạm ứng, thanh toán cuối (giữ nguyên câu chữ, chỉ chuẩn
  hóa bố cục + đưa phần tổng vào trong bảng).
- Chuẩn hóa nhẹ Báo giá & Hợp đồng: chỉ đồng bộ cỡ chữ thân + màu header bảng, KHÔNG
  đổi cấu trúc/nội dung.

Usage:  venv/Scripts/python.exe scripts/std_templates.py <out_dir> [<src_dir>]
"""
import os
import sys
from docx import Document
from docx.shared import Pt, RGBColor, Twips
from docx.enum.text import WD_ALIGN_PARAGRAPH as AL
from docx.enum.table import WD_TABLE_ALIGNMENT as TAL
from docx.enum.section import WD_ORIENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

FONT = 'Times New Roman'
BODY = 13
SMALL = 12
TITLE = 16
SUBTITLE = 13
NAT = 13                      # national header size
BLUE = '2E74B5'              # item-table header fill
LT = 'EEF3FB'               # intermediate total rows
GRAND = 'D9E1F2'            # grand-total row
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BLACK = RGBColor(0, 0, 0)
NBSP = ' '
PAGE_W_TW = 12240            # Letter 8.5"
USABLE_TW = 10800            # 7.5" (8.5 - 2*0.5" margins)


# ── run / paragraph helpers ───────────────────────────────────────────────────
def _run(p, text, size=BODY, bold=False, italic=False, color=None):
    r = p.add_run(text)
    r.font.name = FONT
    r._element.rPr.rFonts.set(qn('w:eastAsia'), FONT)
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.italic = italic
    if color is not None:
        r.font.color.rgb = color
    return r


def _para(container, text='', size=BODY, bold=False, italic=False, align=None,
          color=None, space_after=2, space_before=0):
    p = container.add_paragraph()
    pf = p.paragraph_format
    pf.space_after = Pt(space_after)
    pf.space_before = Pt(space_before)
    pf.line_spacing = 1.15
    if align is not None:
        p.alignment = align
    if text:
        _run(p, text, size, bold, italic, color)
    return p


def _shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = tcPr.find(qn('w:shd'))
    if shd is None:
        shd = OxmlElement('w:shd')
        tcPr.append(shd)
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), fill)


def _vcenter(cell):
    tcPr = cell._tc.get_or_add_tcPr()
    va = tcPr.find(qn('w:vAlign'))
    if va is None:
        va = OxmlElement('w:vAlign'); tcPr.append(va)
    va.set(qn('w:val'), 'center')


def _cell(cell, lines, size=BODY, bold=False, align=AL.LEFT, color=None, italic=False):
    """Write lines (str or list[str]) into a cell, clearing the default paragraph."""
    if isinstance(lines, str):
        lines = [lines]
    cell.text = ''
    p = cell.paragraphs[0]
    for i, ln in enumerate(lines):
        if i:
            p = cell.add_paragraph()
        p.alignment = align
        p.paragraph_format.space_after = Pt(1)
        p.paragraph_format.space_before = Pt(1)
        _run(p, ln, size, bold, italic, color)
    _vcenter(cell)


def _set_grid(table, widths_tw):
    """Force column widths (twips) via tblGrid + per-cell tcW."""
    tbl = table._tbl
    grid = tbl.find(qn('w:tblGrid'))
    if grid is None:
        grid = OxmlElement('w:tblGrid'); tbl.insert(0, grid)
    for g in list(grid.findall(qn('w:gridCol'))):
        grid.remove(g)
    for w in widths_tw:
        gc = OxmlElement('w:gridCol'); gc.set(qn('w:w'), str(w)); grid.append(gc)
    for row in table.rows:
        for cell, w in zip(row.cells, widths_tw):
            tcPr = cell._tc.get_or_add_tcPr()
            tcW = tcPr.find(qn('w:tcW'))
            if tcW is None:
                tcW = OxmlElement('w:tcW'); tcPr.append(tcW)
            tcW.set(qn('w:w'), str(w)); tcW.set(qn('w:type'), 'dxa')


def _borders(table, sz=4):
    tblPr = table._tbl.tblPr
    borders = OxmlElement('w:tblBorders')
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        e = OxmlElement(f'w:{edge}')
        e.set(qn('w:val'), 'single'); e.set(qn('w:sz'), str(sz))
        e.set(qn('w:space'), '0'); e.set(qn('w:color'), '000000')
        borders.append(e)
    tblPr.append(borders)


def _no_borders(table):
    tblPr = table._tbl.tblPr
    borders = OxmlElement('w:tblBorders')
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        e = OxmlElement(f'w:{edge}'); e.set(qn('w:val'), 'none')
        borders.append(e)
    tblPr.append(borders)


def _setup_page(doc):
    s = doc.sections[0]
    s.page_width = Twips(PAGE_W_TW)
    s.page_height = Twips(15840)
    for m in ('left_margin', 'right_margin', 'top_margin', 'bottom_margin'):
        setattr(s, m, Twips(720))   # 0.5"
    # base style font
    st = doc.styles['Normal']
    st.font.name = FONT
    st.font.size = Pt(BODY)
    st.element.rPr.rFonts.set(qn('w:eastAsia'), FONT)


# ── shared blocks ─────────────────────────────────────────────────────────────
def header_block(doc, date_tokens):
    """2-column header: company info (left) | national header + place/date (right)."""
    d, m, y = date_tokens
    t = doc.add_table(rows=1, cols=2)
    t.alignment = TAL.CENTER
    _set_grid(t, [int(USABLE_TW*0.46), int(USABLE_TW*0.54)])
    _no_borders(t)
    left, right = t.rows[0].cells
    # left — company
    left.text = ''
    p = left.paragraphs[0]; p.alignment = AL.LEFT
    _run(p, '{{ company_name }}', SMALL, bold=True)
    for txt in ('Địa chỉ: {{ company_address }}',
                'ĐT: {{ company_phone }}   -   MST: {{ company_tax_code }}',
                'Email: {{ company_email }}'):
        pp = left.add_paragraph(); pp.alignment = AL.LEFT
        pp.paragraph_format.space_after = Pt(0)
        _run(pp, txt, SMALL)
    _vcenter(left)
    # right — national header (one line via NBSP) + place/date
    right.text = ''
    p = right.paragraphs[0]; p.alignment = AL.CENTER
    _run(p, 'CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM'.replace(' ', NBSP), NAT, bold=True)
    for txt, bold, ital in (('Độc lập - Tự do - Hạnh phúc', True, False),
                            ('----------------o0o----------------', False, False)):
        pp = right.add_paragraph(); pp.alignment = AL.CENTER
        pp.paragraph_format.space_after = Pt(0)
        _run(pp, txt, SUBTITLE, bold=bold, italic=ital)
    pp = right.add_paragraph(); pp.alignment = AL.CENTER
    _run(pp, f'{{{{ city }}}}, ngày {{{{ {d} }}}} tháng {{{{ {m} }}}} năm {{{{ {y} }}}}',
         SUBTITLE, italic=True)
    _vcenter(right)
    return t


def title_block(doc, title, subtitle=None, number_token='{{ report_number }}'):
    _para(doc, '', space_after=4)
    _para(doc, title, size=TITLE, bold=True, align=AL.CENTER, space_before=4, space_after=2)
    if subtitle:
        _para(doc, subtitle, size=SUBTITLE, italic=True, align=AL.CENTER, space_after=2)
    _para(doc, f'Số: {number_token}', size=BODY, align=AL.CENTER, space_after=6)


def item_table(doc, headers, cell_tokens, widths_frac, total_rows=None, aligns=None):
    """Item table: header (blue/white) + docxtpl row loop + optional in-table totals.

    total_rows: list of (label, value_token, is_grand). Label spans all but last col.
    """
    ncol = len(headers)
    nrow = 4 + (len(total_rows) if total_rows else 0)
    t = doc.add_table(rows=nrow, cols=ncol)
    t.alignment = TAL.CENTER
    _set_grid(t, [int(USABLE_TW*f) for f in widths_frac])
    _borders(t)
    aligns = aligns or [AL.CENTER]*ncol
    # header row
    for c, h in zip(t.rows[0].cells, headers):
        _shade(c, BLUE)
        _cell(c, h, size=SMALL, bold=True, align=AL.CENTER, color=WHITE)
    # loop directive rows
    _cell(t.rows[1].cells[0], '{%tr for item in items %}', size=SMALL)
    _cell(t.rows[3].cells[0], '{%tr endfor %}', size=SMALL)
    # data row
    for i, (c, tok) in enumerate(zip(t.rows[2].cells, cell_tokens)):
        _cell(c, tok, size=BODY, align=aligns[i])
    # total rows (merged label | value)
    if total_rows:
        for k, (label, value, grand) in enumerate(total_rows):
            row = t.rows[4+k]
            merged = row.cells[0]
            for j in range(1, ncol-1):
                merged = merged.merge(row.cells[j])
            fill = GRAND if grand else LT
            _shade(merged, fill); _shade(row.cells[-1], fill)
            _cell(merged, label, size=BODY, bold=grand, align=AL.RIGHT)
            _cell(row.cells[-1], value, size=BODY, bold=grand, align=AL.RIGHT)
    return t


def signature_block(doc, left_label, right_label, left_sub='(Ký, ghi rõ họ tên)',
                    right_sub='(Ký, ghi rõ họ tên)', right_name='{{ company_representative }}'):
    _para(doc, '', space_after=2)
    t = doc.add_table(rows=1, cols=2)
    t.alignment = TAL.CENTER
    _set_grid(t, [USABLE_TW//2, USABLE_TW//2])
    _no_borders(t)
    l, r = t.rows[0].cells
    _cell(l, [left_label, left_sub], size=BODY, bold=True, align=AL.CENTER)
    # the sub line should not be bold
    l.paragraphs[1].runs[0].font.bold = False
    l.paragraphs[1].runs[0].font.italic = True
    _cell(r, [right_label, right_sub], size=BODY, bold=True, align=AL.CENTER)
    r.paragraphs[1].runs[0].font.bold = False
    r.paragraphs[1].runs[0].font.italic = True
    # leave vertical space for the wet signature
    for cell in (l, r):
        for _ in range(4):
            cell.add_paragraph()
    return t


# ── document builders ─────────────────────────────────────────────────────────
def build_delivery(path):
    doc = Document(); _setup_page(doc)
    header_block(doc, ('report_day', 'report_month', 'report_year'))
    title_block(doc, 'BIÊN BẢN BÀN GIAO & NGHIỆM THU')
    _para(doc, 'Căn cứ hợp đồng/đơn hàng số {{ order_code }} - {{ order_title }};')
    _para(doc, 'Hôm nay, ngày {{ handover_day }} tháng {{ handover_month }} năm '
               '{{ handover_year }}, tại {{ handover_location }}, chúng tôi gồm:')
    _para(doc, 'BÊN GIAO (BÊN BÁN): {{ company_name }}', bold=True)
    _para(doc, '   - Đại diện: {{ company_representative }}   -   Chức vụ: '
               '{{ company_representative_title }}')
    _para(doc, 'BÊN NHẬN (KHÁCH HÀNG): {{ customer_name }}', bold=True)
    _para(doc, '   - Đại diện: {{ customer_representative }}   -   Điện thoại: '
               '{{ customer_phone }}')
    _para(doc, '   - Địa chỉ: {{ customer_address }}')
    _para(doc, 'Hai bên cùng tiến hành bàn giao và nghiệm thu các hạng mục sau:')
    item_table(
        doc,
        headers=['STT', 'Nội dung công việc / Hàng hóa', 'ĐVT', 'SL đặt', 'SL giao',
                 'SL nghiệm thu', 'Kết quả'],
        cell_tokens=['{{ item.stt }}', '{{ item.name }}', '{{ item.unit }}',
                     '{{ item.quantity }}', '{{ item.delivered_qty }}',
                     '{{ item.accepted_qty }}', '{{ item.accepted }}'],
        widths_frac=[0.075, 0.325, 0.09, 0.11, 0.11, 0.13, 0.16],
        aligns=[AL.CENTER, AL.LEFT, AL.CENTER, AL.CENTER, AL.CENTER, AL.CENTER, AL.CENTER],
    )
    _para(doc, 'Tình trạng sản phẩm khi bàn giao: {{ product_condition }}', space_before=4)
    _para(doc, 'Ghi chú: {{ notes }}')
    _para(doc, 'Kết luận: Bên nhận đã kiểm tra và ĐỒNG Ý nghiệm thu các hạng mục đạt '
               'yêu cầu nêu trên.')
    _para(doc, 'Biên bản được lập thành {{ copies_count }} bản, mỗi bên giữ một bản có '
               'giá trị pháp lý như nhau.')
    signature_block(doc, 'ĐẠI DIỆN BÊN NHẬN', 'ĐẠI DIỆN BÊN GIAO')
    doc.save(path)


def _payment_common(doc, title, subtitle, lead):
    header_block(doc, ('report_day', 'report_month', 'report_year'))
    title_block(doc, title, subtitle=subtitle)
    _para(doc, 'Kính gửi: Quý khách hàng {{ customer_name }}', bold=True)
    _para(doc, lead)


def _payment_tail(doc):
    _para(doc, 'Bằng chữ: {{ amount_in_words }}', italic=True, space_before=4)
    _para(doc, 'Nội dung: {{ work_completed_summary }}')
    _para(doc, 'THÔNG TIN THANH TOÁN:', bold=True, space_before=2)
    _para(doc, '   - Ngân hàng: {{ company_bank_name }}')
    _para(doc, '   - Số tài khoản: {{ company_bank_account_number }}')
    _para(doc, '   - Chủ tài khoản: {{ company_bank_account_holder }}')
    _para(doc, 'Rất mong Quý khách thu xếp theo đề nghị trên. Trân trọng cảm ơn!',
          space_before=2)
    signature_block(doc, 'KHÁCH HÀNG', 'ĐẠI DIỆN CÔNG TY')


PAY_HEADERS = ['STT', 'Nội dung', 'ĐVT', 'Số lượng', 'Đơn giá (VNĐ)', 'Thành tiền (VNĐ)']
PAY_TOKENS = ['{{ item.stt }}', '{{ item.name }}', '{{ item.unit }}',
              '{{ item.quantity }}', '{{ item.unit_price }}', '{{ item.total }}']
PAY_WIDTHS = [0.07, 0.37, 0.10, 0.13, 0.16, 0.17]
PAY_ALIGN = [AL.CENTER, AL.LEFT, AL.CENTER, AL.CENTER, AL.RIGHT, AL.RIGHT]


def build_payment_advance(path):
    doc = Document(); _setup_page(doc)
    _payment_common(
        doc, 'GIẤY ĐỀ NGHỊ TẠM ỨNG', None,
        '{{ company_name }} trân trọng đề nghị Quý khách tạm ứng cho đơn hàng '
        '{{ order_code }} - {{ order_title }} theo nội dung sau:')
    item_table(
        doc, PAY_HEADERS, PAY_TOKENS, PAY_WIDTHS, aligns=PAY_ALIGN,
        total_rows=[
            ('Cộng tiền hàng:', '{{ subtotal }}', False),
            ('Thuế VAT {{ vat_rate }}%:', '{{ vat_amount }}', False),
            ('Tổng giá trị hợp đồng (đã gồm VAT):', '{{ contract_value }}', False),
            ('Tỷ lệ tạm ứng: {{ advance_percentage }}%', '', False),
            ('SỐ TIỀN ĐỀ NGHỊ TẠM ỨNG:', '{{ advance_amount }}', True),
            ('Còn lại thanh toán sau khi bàn giao:', '{{ remaining_amount }}', False),
        ])
    _payment_tail(doc)
    doc.save(path)


def build_payment_final(path):
    doc = Document(); _setup_page(doc)
    _payment_common(
        doc, 'GIẤY ĐỀ NGHỊ THANH TOÁN', '(Thanh toán đợt cuối sau bàn giao)',
        '{{ company_name }} trân trọng đề nghị Quý khách thanh toán phần còn lại cho '
        'đơn hàng {{ order_code }} - {{ order_title }} đã hoàn thành bàn giao, theo '
        'nội dung sau:')
    item_table(
        doc, PAY_HEADERS, PAY_TOKENS, PAY_WIDTHS, aligns=PAY_ALIGN,
        total_rows=[
            ('Cộng tiền hàng:', '{{ subtotal }}', False),
            ('Thuế VAT {{ vat_rate }}%:', '{{ vat_amount }}', False),
            ('Tổng giá trị hợp đồng (đã gồm VAT):', '{{ contract_value }}', False),
            ('Đã tạm ứng ({{ advance_percentage }}%):', '{{ advance_amount }}', False),
            ('CÒN LẠI PHẢI THANH TOÁN:', '{{ remaining_amount }}', True),
        ])
    _payment_tail(doc)
    doc.save(path)


# ── light normalization for quotation & contract (font size + header color only) ──
def normalize_inplace(src, dst):
    doc = Document(src)
    st = doc.styles['Normal']; st.font.name = FONT; st.font.size = Pt(BODY)
    try:
        st.element.rPr.rFonts.set(qn('w:eastAsia'), FONT)
    except Exception:
        pass

    def fix_runs(paragraph):
        for r in paragraph.runs:
            r.font.name = FONT
            try:
                r._element.rPr.rFonts.set(qn('w:eastAsia'), FONT)
            except Exception:
                pass
            if r.font.size and r.font.size.pt < 15:      # body text → 13pt, keep titles
                r.font.size = Pt(BODY)

    for p in doc.paragraphs:
        fix_runs(p)
    for t in doc.tables:
        for row in t.rows:
            for c in row.cells:
                for p in c.paragraphs:
                    fix_runs(p)
    doc.save(dst)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else '.'
    src = sys.argv[2] if len(sys.argv) > 2 else out
    os.makedirs(out, exist_ok=True)
    build_delivery(os.path.join(out, 'delivery_45babaf8.docx'))
    build_payment_advance(os.path.join(out, 'payment_advance_template.docx'))
    build_payment_final(os.path.join(out, 'payment_final_template.docx'))
    print('built: delivery, payment_advance, payment_final')
    for fn in ('quotation_2d1aefda.docx', 'contract_ac649e49.docx'):
        s = os.path.join(src, fn)
        if os.path.exists(s):
            normalize_inplace(s, os.path.join(out, fn))
            print('normalized:', fn)


if __name__ == '__main__':
    main()
