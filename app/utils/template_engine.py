"""
Document template engine - handles RTF templates and document generation
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


class DocumentVariableCollector:
    """Collects variables needed for document generation"""
    
    @staticmethod
    def collect_quotation_variables(quotation, customer, order):
        """Collect variables for quotation document"""
        items_list = quotation.items or []
        items_text = '\n'.join([
            f"  {item.get('name', '')}: {item.get('quantity', 0)} x {item.get('unit_price', 0)} = {item.get('total', 0)}"
            for item in items_list
        ])
        
        return {
            'quotation_number': quotation.quotation_number,
            'quotation_date': quotation.quotation_date.strftime('%Y-%m-%d') if quotation.quotation_date else '',
            'validity_days': str(quotation.validity_days),
            'customer_name': customer.name,
            'customer_code': customer.customer_code,
            'customer_phone': customer.phone or '',
            'customer_email': customer.email or '',
            'customer_address': customer.address or '',
            'customer_city': customer.city or '',
            'customer_postal_code': customer.postal_code or '',
            'order_code': order.order_code,
            'order_title': order.title,
            'items': items_text,
            'total_amount': str(quotation.total_amount),
            'notes': quotation.notes or '',
            'generated_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
    
    @staticmethod
    def collect_contract_variables(contract, quotation, customer, order):
        """Collect variables for contract document"""
        return {
            'contract_number': contract.contract_number,
            'contract_date': contract.contract_date.strftime('%Y-%m-%d') if contract.contract_date else '',
            'quotation_number': quotation.quotation_number if quotation else '',
            'customer_name': customer.name,
            'customer_code': customer.customer_code,
            'customer_phone': customer.phone or '',
            'customer_email': customer.email or '',
            'customer_address': customer.address or '',
            'order_code': order.order_code,
            'order_title': order.title,
            'contract_value': str(contract.contract_value),
            'terms_and_conditions': contract.terms_and_conditions or '',
            'generated_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
    
    @staticmethod
    def collect_delivery_variables(delivery_report, customer, order):
        """Collect variables for delivery report"""
        return {
            'report_number': delivery_report.report_number,
            'report_date': delivery_report.report_date.strftime('%Y-%m-%d') if delivery_report.report_date else '',
            'delivery_date': delivery_report.delivery_date.strftime('%Y-%m-%d') if delivery_report.delivery_date else '',
            'customer_name': customer.name,
            'customer_code': customer.customer_code,
            'order_code': order.order_code,
            'order_title': order.title,
            'work_description': delivery_report.work_description or '',
            'materials_used': delivery_report.materials_used or '',
            'notes': delivery_report.notes or '',
            'generated_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
    
    @staticmethod
    def collect_payment_variables(payment_report, customer, order):
        """Collect variables for payment report"""
        return {
            'report_number': payment_report.report_number,
            'payment_type': payment_report.payment_type,
            'report_date': payment_report.report_date.strftime('%Y-%m-%d') if payment_report.report_date else '',
            'payment_date': payment_report.payment_date.strftime('%Y-%m-%d') if payment_report.payment_date else '',
            'customer_name': customer.name,
            'customer_code': customer.customer_code,
            'order_code': order.order_code,
            'order_title': order.title,
            'amount': str(payment_report.amount),
            'payment_method': payment_report.payment_method or '',
            'transaction_reference': payment_report.transaction_reference or '',
            'notes': payment_report.notes or '',
            'generated_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
