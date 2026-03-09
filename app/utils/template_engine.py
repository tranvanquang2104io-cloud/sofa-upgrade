"""
Document template engine - handles RTF and DOCX templates (via docxtpl) and document generation.

Two engines are available:
  - DocxTemplateEngine  : modern engine using docxtpl + Jinja2 (recommended)
  - TemplateEngine      : legacy text / placeholder-based engine (kept for backward-compat)
"""
import os
import re
import json
from datetime import datetime
from io import BytesIO
from flask import current_app
from docx import Document as DocxDocument
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
import logging

logger = logging.getLogger(__name__)


class TemplateEngine:
    """
    Template engine for processing RTF templates and generating documents
    """
    
    # Variable pattern - matches {{variable_name}}
    VARIABLE_PATTERN = r'\{\{(\w+)\}\}'
    
    @staticmethod
    def extract_variables(template_content):
        """
        Extract all variables from template
        
        Args:
            template_content: RTF or text template content
            
        Returns:
            list: List of variable names found in template
        """
        matches = re.findall(TemplateEngine.VARIABLE_PATTERN, template_content)
        return list(set(matches))
    
    @staticmethod
    def render_template(template_content, variables_dict):
        """
        Render template by replacing variables with values
        
        Args:
            template_content: Template content with {{variable}} placeholders
            variables_dict: Dictionary of {variable_name: value}
            
        Returns:
            str: Rendered content with variables replaced
        """
        rendered = template_content
        
        for var_name, value in variables_dict.items():
            # Handle None and empty values
            if value is None:
                value = ''
            elif not isinstance(value, str):
                value = str(value)
            
            placeholder = f'{{{{{var_name}}}}}'
            rendered = rendered.replace(placeholder, value)
        
        # Replace any unreplaced variables with empty string
        rendered = re.sub(TemplateEngine.VARIABLE_PATTERN, '', rendered)
        
        return rendered
    
    @staticmethod
    def rtf_to_text(rtf_content):
        """
        Convert RTF content to plain text
        
        Args:
            rtf_content: RTF formatted content
            
        Returns:
            str: Plain text without RTF formatting
        """
        # Simple RTF stripping - removes common RTF control sequences
        # For production, consider using striprtf library
        text = re.sub(r'\\[a-z]+\d*\s?', '', rtf_content)
        text = re.sub(r'[{}]', '', text)
        return text.strip()
    
    @staticmethod
    def create_docx_document(rendered_content, document_title="Generated Document"):
        """
        Create a DOCX document from rendered content
        
        Args:
            rendered_content: Text content to include in document
            document_title: Title of the document
            
        Returns:
            BytesIO: DOCX document in bytes
        """
        doc = DocxDocument()
        
        # Add title
        title = doc.add_heading(document_title, 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Add generated date
        date_para = doc.add_paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        date_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        
        # Process content - handle paragraphs
        for line in rendered_content.split('\n'):
            if line.strip():
                doc.add_paragraph(line)
        
        # Convert to bytes
        output = BytesIO()
        doc.save(output)
        output.seek(0)
        return output
    
    @staticmethod
    def generate_pdf_from_docx(docx_bytes, output_path):
        """
        Convert DOCX to PDF using LibreOffice
        
        Args:
            docx_bytes: DOCX document as bytes
            output_path: Path to save PDF
            
        Returns:
            bool: True if successful
        """
        try:
            import subprocess
            import tempfile
            
            # Save DOCX temporarily
            with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
                tmp.write(docx_bytes.getvalue() if isinstance(docx_bytes, BytesIO) else docx_bytes)
                tmp_path = tmp.name
            
            try:
                # Use LibreOffice to convert
                result = subprocess.run([
                    'soffice',
                    '--headless',
                    '--convert-to', 'pdf',
                    '--outdir', os.path.dirname(output_path),
                    tmp_path
                ], capture_output=True, timeout=30)
                
                if result.returncode == 0:
                    # LibreOffice creates PDF with same base name
                    base_name = os.path.splitext(os.path.basename(tmp_path))[0]
                    source_pdf = os.path.join(os.path.dirname(output_path), f'{base_name}.pdf')
                    if os.path.exists(source_pdf):
                        os.rename(source_pdf, output_path)
                        logger.info(f"PDF generated successfully: {output_path}")
                        return True
                else:
                    logger.error(f"LibreOffice conversion failed: {result.stderr.decode()}")
                    return False
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                    
        except Exception as e:
            logger.error(f"Error generating PDF: {str(e)}")
            return False
    
    @staticmethod
    def fallback_pdf_generation(content, output_path):
        """
        Fallback PDF generation using reportlab (basic)
        
        Args:
            content: Text content
            output_path: Path to save PDF
            
        Returns:
            bool: True if successful
        """
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.enums import TA_CENTER, TA_LEFT
            
            doc = SimpleDocTemplate(output_path, pagesize=letter)
            story = []
            styles = getSampleStyleSheet()
            
            # Add title paragraph
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=16,
                textColor=RGBColor(0, 0, 0),
                spaceAfter=30,
                alignment=TA_CENTER
            )
            
            body_style = ParagraphStyle(
                'CustomBody',
                parent=styles['BodyText'],
                fontSize=11,
                alignment=TA_LEFT,
                spaceAfter=12
            )
            
            story.append(Paragraph("Generated Document", title_style))
            story.append(Spacer(1, 0.3*inch))
            
            # Add content paragraphs
            for line in content.split('\n'):
                if line.strip():
                    story.append(Paragraph(line, body_style))
            
            doc.build(story)
            logger.info(f"PDF generated successfully (reportlab): {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error generating PDF with reportlab: {str(e)}")
            return False


class DocxTemplateEngine:
    """
    Modern template engine that renders .docx templates via docxtpl + Jinja2.

    Template design (Microsoft Word):
      - Use {{ variable }} for scalar substitutions.
      - For repeating table rows, put {%tr for item in items %} in the first cell
        of the row to repeat, and {%tr endfor %} in the last cell of that row.
      - Use {{ loop.index }} for row numbers inside loops.
      - Conditional blocks: {% if condition %}...{% endif %}

    Context is built by DocumentVariableCollector.collect_*_variables().
    Items lists contain dicts:  {stt, name, unit, quantity, unit_price, total, notes}
    """

    @staticmethod
    def _inject_inline_images(tpl, context: dict) -> None:
        """
        Walk context lists and replace ``image_path`` strings in item dicts
        with ``docxtpl.InlineImage`` objects so that {{ item.image }} tags in
        .docx templates render the actual picture.

        Images are sized to 3 cm wide by default; the aspect ratio is preserved.
        """
        try:
            from docxtpl import InlineImage
            from docx.shared import Cm
            upload_root = os.path.join(os.path.dirname(__file__), '..', 'uploads')
            upload_root = os.path.normpath(upload_root)
        except ImportError:
            return

        for val in context.values():
            if not isinstance(val, list):
                continue
            for item in val:
                if not isinstance(item, dict):
                    continue
                path_rel = item.get('image_path')
                if not path_rel:
                    item['image'] = ''
                    continue
                full_path = os.path.join(upload_root, path_rel)
                if os.path.exists(full_path):
                    try:
                        item['image'] = InlineImage(tpl, full_path, width=Cm(4))
                    except Exception:
                        item['image'] = ''
                else:
                    item['image'] = ''

    @staticmethod
    def render(template_path: str, context: dict) -> BytesIO:
        """
        Render a .docx template and return a BytesIO DOCX.

        Args:
            template_path: Absolute path to the .docx template file.
            context:        Jinja2 context dict (scalars + lists for table loops).

        Returns:
            BytesIO: Rendered DOCX document.
        """
        from docxtpl import DocxTemplate
        tpl = DocxTemplate(template_path)
        DocxTemplateEngine._inject_inline_images(tpl, context)
        tpl.render(context)
        output = BytesIO()
        tpl.save(output)
        output.seek(0)
        return output

    @staticmethod
    def render_to_file(template_path: str, context: dict, output_path: str) -> None:
        """Render template and save to output_path (creates parent dirs if needed)."""
        from docxtpl import DocxTemplate
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        tpl = DocxTemplate(template_path)
        DocxTemplateEngine._inject_inline_images(tpl, context)
        tpl.render(context)
        tpl.save(output_path)

    @staticmethod
    def is_docx_template(template_file: str) -> bool:
        """Return True if the template file is a DOCX file."""
        return (template_file or '').lower().endswith('.docx')


# ---------------------------------------------------------------------------
# Helper: number formatter
# ---------------------------------------------------------------------------

def _fmt(value, decimals=0) -> str:
    """Format a numeric value with thousands separator."""
    try:
        v = float(value) if value is not None else 0
        if decimals:
            return f"{v:,.{decimals}f}"
        return f"{v:,.0f}"
    except (TypeError, ValueError):
        return str(value) if value is not None else ''


def _fmt_date(d, fmt='%d/%m/%Y') -> str:
    """Format a date / datetime to string."""
    if d is None:
        return ''
    try:
        return d.strftime(fmt)
    except AttributeError:
        return str(d)


def _date_parts(d) -> tuple:
    """Return (day, month, year) as zero-padded strings, e.g. ('03', '02', '2026')."""
    if d is None:
        return ('', '', '')
    try:
        return (d.strftime('%d'), d.strftime('%m'), d.strftime('%Y'))
    except AttributeError:
        # Try to parse from 'DD/MM/YYYY' string fallback
        try:
            from datetime import datetime as _dt
            parsed = _dt.strptime(str(d), '%d/%m/%Y')
            return (parsed.strftime('%d'), parsed.strftime('%m'), parsed.strftime('%Y'))
        except Exception:
            return ('', '', '')


class DocumentVariableCollector:
    """
    Builds Jinja2 context dicts for each document type.

    All collectors accept an optional ``company`` kwarg so that company
    header information (name, address, phone) can be embedded in the
    template.  Items lists are returned as a list-of-dicts so that
    DocxTemplateEngine can loop over them in table rows.
    """

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_items(raw_items: list) -> list:
        """Convert raw JSON items list to template-friendly dicts."""
        result = []
        for i, item in enumerate(raw_items or []):
            result.append({
                'stt':        str(i + 1),
                'name':       item.get('name', ''),
                'unit':       item.get('unit', 'Cái'),
                'quantity':   _fmt(item.get('quantity', 0)),
                'unit_price': _fmt(item.get('unit_price', 0)),
                'total':      _fmt(item.get('total', 0)),
                'notes':      item.get('notes', ''),
                'image_path': item.get('image_path') or '',  # preserved for InlineImage injection
                'image':      '',  # placeholder; overwritten by _inject_inline_images
            })
        return result

    @staticmethod
    def _company_ctx(company) -> dict:
        if company is None:
            return {
                'company_name': '',
                'company_address': '',
                'company_production_address': '',
                'company_phone': '',
                'company_email': '',
                'company_tax_code': '',
                'company_representative_name': '',
                'company_representative_title': '',
                'company_vat_rate': '8',
                'company_bank_accounts': [],
            }
        bank_accounts = getattr(company, 'bank_accounts', None) or []
        # Flatten first bank for convenience
        first_bank = bank_accounts[0] if bank_accounts else {}
        return {
            'company_name':                getattr(company, 'name', ''),
            'company_address':             getattr(company, 'address', '') or '',
            'company_production_address':  getattr(company, 'production_address', '') or '',
            'company_phone':               getattr(company, 'phone', '') or '',
            'company_email':               getattr(company, 'email', '') or '',
            'company_tax_code':            getattr(company, 'tax_code', '') or '',
            'company_representative_name': getattr(company, 'representative_name', '') or '',
            'company_representative_title': getattr(company, 'representative_title', '') or '',
            'company_vat_rate':            str(getattr(company, 'vat_rate', 8) or 8),
            'company_bank_accounts':       bank_accounts,
            'company_bank_name':           first_bank.get('bank_name', ''),
            'company_bank_account_number': first_bank.get('account_number', ''),
            'company_bank_account_holder': first_bank.get('account_holder', ''),
        }

    # ------------------------------------------------------------------
    # Public collectors
    # ------------------------------------------------------------------

    @staticmethod
    def collect_quotation_variables(quotation, customer, order, company=None):
        """Context for quotation document."""
        ctx = DocumentVariableCollector._company_ctx(company)
        ctx.update({
            # Quotation header
            'quotation_number': quotation.quotation_number,
            'quotation_date':   _fmt_date(quotation.quotation_date),
            'quotation_day':    _date_parts(quotation.quotation_date)[0],
            'quotation_month':  _date_parts(quotation.quotation_date)[1],
            'quotation_year':   _date_parts(quotation.quotation_date)[2],
            'validity_days':    str(quotation.validity_days or 30),
            'city':             getattr(quotation, 'city', '') or '',
            # Customer
            'customer_name':              customer.name,
            'customer_code':              customer.customer_code,
            'customer_phone':             customer.phone or '',
            'customer_email':             customer.email or '',
            'customer_address':           customer.address or '',
            'customer_city':              customer.city or '',
            'customer_postal_code':       customer.postal_code or '',
            'customer_tax_code':          getattr(customer, 'tax_code', '') or '',
            'customer_representative':    getattr(customer, 'representative_name', '') or '',
            'customer_representative_title': getattr(customer, 'representative_title', '') or '',
            # Order
            'order_code':  order.order_code,
            'order_title': order.title,
            # Items (list → table loop)
            'items':        DocumentVariableCollector._build_items(quotation.items),
            # Financials
            'subtotal':     _fmt(getattr(quotation, 'subtotal', 0) or 0),
            'vat_rate':     str(getattr(quotation, 'vat_rate', 8) or 8),
            'vat_amount':   _fmt(getattr(quotation, 'vat_amount', 0) or 0),
            'total_amount': _fmt(quotation.total_amount),
            'amount_in_words': getattr(quotation, 'amount_in_words', '') or '',
            # Payment terms / misc
            'payment_terms':  getattr(quotation, 'payment_terms', '') or '',
            'notes':          quotation.notes or '',
            'generated_date': datetime.now().strftime('%d/%m/%Y %H:%M'),
        })
        return ctx

    @staticmethod
    def collect_contract_variables(contract, quotation, customer, order, company=None):
        """Context for contract document."""
        ctx = DocumentVariableCollector._company_ctx(company)

        # Override company bank info with the selected bank account on this contract
        selected_bank_index = int(getattr(contract, 'selected_bank_index', 0) or 0)
        bank_accounts = getattr(company, 'bank_accounts', None) or [] if company else []
        if bank_accounts and selected_bank_index < len(bank_accounts):
            selected_bank = bank_accounts[selected_bank_index]
        elif bank_accounts:
            selected_bank = bank_accounts[0]
        else:
            selected_bank = {}
        ctx['company_bank_name']           = selected_bank.get('bank_name', '')
        ctx['company_bank_account_number'] = selected_bank.get('account_number', '')
        ctx['company_bank_account_holder'] = selected_bank.get('account_holder', '')

        ctx.update({
            # Contract header
            'contract_number': contract.contract_number,
            'contract_date':   _fmt_date(contract.contract_date),
            'contract_day':    _date_parts(contract.contract_date)[0],
            'contract_month':  _date_parts(contract.contract_date)[1],
            'contract_year':   _date_parts(contract.contract_date)[2],
            # Contract start date (ngày bắt đầu thực hiện)
            'contract_start_date':       _fmt_date(getattr(contract, 'contract_start_date', None)),
            'contract_start_day':        _date_parts(getattr(contract, 'contract_start_date', None))[0],
            'contract_start_month':      _date_parts(getattr(contract, 'contract_start_date', None))[1],
            'contract_start_year':       _date_parts(getattr(contract, 'contract_start_date', None))[2],
            # Financials
            'contract_value':  _fmt(contract.contract_value),
            'total_amount':    _fmt(contract.contract_value),  # alias
            'amount_in_words': getattr(contract, 'amount_in_words', '') or '',
            'city':            getattr(contract, 'city', '') or '',
            # Completion & cancellation
            'contract_days_complete': str(getattr(contract, 'contract_days_complete', 30) or 30),
            'num_date_notice_cancel': str(getattr(contract, 'num_date_notice_cancel', 7) or 7),
            # Contract content from order description
            'contract_content': getattr(order, 'description', '') or '',
            # Related quotation
            'quotation_number': quotation.quotation_number if quotation else '',
            # Customer
            'customer_name':              customer.name,
            'customer_code':              customer.customer_code,
            'customer_phone':             customer.phone or '',
            'customer_email':             customer.email or '',
            'customer_address':           customer.address or '',
            'customer_tax_code':          getattr(customer, 'tax_code', '') or '',
            'customer_representative':    getattr(customer, 'representative_name', '') or '',
            'customer_representative_title': getattr(customer, 'representative_title', '') or '',
            # Order
            'order_code':  order.order_code,
            'order_title': order.title,
            # Items (list → table loop)
            'items': DocumentVariableCollector._build_items(
                contract.items or (quotation.items if quotation else [])
            ),
            # Financials
            'subtotal':           _fmt(getattr(contract, 'subtotal', 0) or 0),
            'vat_rate':           str(getattr(contract, 'vat_rate', 8) or 8),
            'vat_amount':         _fmt(getattr(contract, 'vat_amount', 0) or 0),
            'advance_percentage': str(getattr(contract, 'advance_percentage', 30) or 30),
            'advance_amount':     _fmt(getattr(contract, 'advance_amount', 0) or 0),
            # Terms, misc
            'terms_and_conditions': contract.terms_and_conditions or '',
            'notes':                getattr(contract, 'notes', '') or '',
            'generated_date':       datetime.now().strftime('%d/%m/%Y %H:%M'),
        })
        return ctx

    @staticmethod
    def collect_delivery_variables(delivery_report, customer, order, company=None):
        """Context for handover / delivery record."""
        ctx = DocumentVariableCollector._company_ctx(company)
        # Build items with acceptance columns
        raw_items = delivery_report.items or []
        handover_items = []
        for i, item in enumerate(raw_items):
            handover_items.append({
                'stt':              str(i + 1),
                'name':             item.get('name', ''),
                'unit':             item.get('unit', 'Cái'),
                'quantity':         _fmt(item.get('quantity', 0)),
                'delivered_qty':    _fmt(item.get('delivered_qty', item.get('quantity', 0))),
                'accepted_qty':     _fmt(item.get('accepted_qty', item.get('quantity', 0))),
                'accepted':         'Đạt' if item.get('accepted', True) else 'Không đạt',
                'rejection_reason': item.get('rejection_reason', ''),
                'notes':            item.get('notes', ''),
            })
        ctx.update({
            # Report header
            'report_number': delivery_report.report_number,
            'report_date':   _fmt_date(delivery_report.report_date),
            'report_day':    _date_parts(delivery_report.report_date)[0],
            'report_month':  _date_parts(delivery_report.report_date)[1],
            'report_year':   _date_parts(delivery_report.report_date)[2],
            'handover_date': _fmt_date(delivery_report.handover_date),
            'handover_day':  _date_parts(delivery_report.handover_date)[0],
            'handover_month': _date_parts(delivery_report.handover_date)[1],
            'handover_year': _date_parts(delivery_report.handover_date)[2],
            'delivery_date': _fmt_date(delivery_report.handover_date),
            # Location / timing
            'handover_location': getattr(delivery_report, 'handover_location', '') or '',
            'start_time':        str(getattr(delivery_report, 'start_time', '') or ''),
            'end_time':          str(getattr(delivery_report, 'end_time', '') or ''),
            'copies_count':      str(getattr(delivery_report, 'copies_count', 2) or 2),
            # Customer
            'customer_name':              customer.name,
            'customer_code':              customer.customer_code,
            'customer_phone':             customer.phone or '',
            'customer_address':           customer.address or '',
            'customer_tax_code':          getattr(customer, 'tax_code', '') or '',
            'customer_representative':    getattr(customer, 'representative_name', '') or delivery_report.customer_representative or '',
            'customer_representative_title': getattr(delivery_report, 'customer_representative_title', '') or '',
            # Order
            'order_code':  order.order_code,
            'order_title': order.title,
            # Items list
            'items': handover_items,
            # Financials
            'subtotal':     _fmt(getattr(delivery_report, 'subtotal', 0) or 0),
            'vat_rate':     str(getattr(delivery_report, 'vat_rate', 8) or 8),
            'vat_amount':   _fmt(getattr(delivery_report, 'vat_amount', 0) or 0),
            'total_amount': _fmt(getattr(delivery_report, 'total_amount', 0) or 0),
            # Representatives
            'company_representative':      delivery_report.company_representative or '',
            'company_representative_title': getattr(delivery_report, 'company_representative_title', '') or '',
            'product_condition':           delivery_report.product_condition or '',
            'notes':                       delivery_report.notes or '',
            'generated_date':              datetime.now().strftime('%d/%m/%Y %H:%M'),
        })
        return ctx

    @staticmethod
    def collect_payment_variables(payment_report, customer, order, company=None, contract=None):
        """Context for payment report."""
        payment_type_display = {
            'advance': 'Tạm ứng (Advance)',
            'final':   'Thanh toán cuối (Final)',
        }.get(payment_report.payment_type, payment_report.payment_type)

        ctx = DocumentVariableCollector._company_ctx(company)
        ctx.update({
            # Report header
            'report_number':        payment_report.report_number,
            'payment_type':         payment_report.payment_type,
            'payment_type_display': payment_type_display,
            'report_date':          _fmt_date(payment_report.report_date),
            'report_day':           _date_parts(payment_report.report_date)[0],
            'report_month':         _date_parts(payment_report.report_date)[1],
            'report_year':          _date_parts(payment_report.report_date)[2],
            'payment_date':         _fmt_date(payment_report.payment_date),
            'payment_day':          _date_parts(payment_report.payment_date)[0],
            'payment_month':        _date_parts(payment_report.payment_date)[1],
            'payment_year':         _date_parts(payment_report.payment_date)[2],
            'quotation_reference_date': _fmt_date(getattr(payment_report, 'quotation_reference_date', None)),
            # Customer
            'customer_name':              customer.name,
            'customer_code':              customer.customer_code,
            'customer_phone':             customer.phone or '',
            'customer_address':           customer.address or '',
            'customer_tax_code':          getattr(customer, 'tax_code', '') or '',
            'customer_representative':    getattr(customer, 'representative_name', '') or '',
            'customer_representative_title': getattr(customer, 'representative_title', '') or '',
            # Order
            'order_code':  order.order_code,
            'order_title': order.title,
            # Items (list → table loop)
            'items': DocumentVariableCollector._build_items(
                getattr(payment_report, 'items', None) or []
            ),
            # Financials
            'subtotal':           _fmt(getattr(payment_report, 'subtotal', 0) or 0),
            'vat_rate':           str(getattr(payment_report, 'vat_rate', 8) or 8),
            'vat_amount':         _fmt(getattr(payment_report, 'vat_amount', 0) or 0),
            'amount':             _fmt(payment_report.amount),
            'advance_percentage': str(getattr(payment_report, 'advance_percentage', 30) or 30),
            'advance_amount':     _fmt(getattr(payment_report, 'advance_amount', 0) or 0),
            'remaining_amount':   _fmt(getattr(payment_report, 'remaining_amount', 0) or 0),
            'amount_in_words':    getattr(payment_report, 'amount_in_words', '') or '',
            # Work summary / bank
            'work_completed_summary': getattr(payment_report, 'work_completed_summary', '') or '',
            'bank_account_info':      getattr(payment_report, 'bank_account_info', None) or [],
            # Legacy payment fields
            'payment_method':        payment_report.payment_method or '',
            'transaction_reference': payment_report.transaction_reference or '',
            # Contract reference
            'contract_number':    getattr(contract, 'contract_number', '') if contract else '',
            'contract_date':      _fmt_date(getattr(contract, 'contract_date', None)) if contract else '',
            'contract_day':       _date_parts(getattr(contract, 'contract_date', None) if contract else None)[0],
            'contract_month':     _date_parts(getattr(contract, 'contract_date', None) if contract else None)[1],
            'contract_year':      _date_parts(getattr(contract, 'contract_date', None) if contract else None)[2],
            'contract_value':     _fmt(getattr(contract, 'contract_value', 0) or 0) if contract else '',
            'advance_percentage_contract': str(getattr(contract, 'advance_percentage', 30) or 30) if contract else '',
            'advance_amount_contract':     _fmt(getattr(contract, 'advance_amount', 0) or 0) if contract else '',
            # Misc
            'notes':          payment_report.notes or '',
            'generated_date': datetime.now().strftime('%d/%m/%Y %H:%M'),
        })
        return ctx
