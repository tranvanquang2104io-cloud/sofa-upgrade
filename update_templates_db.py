"""Update document templates in database with new clean text format"""
from app import create_app
from app.models.models import DocumentTemplate
from app.config.database import db
import os

app = create_app()

template_files = {
    'quotation': 'quotation_template.rtf',
    'contract': 'contract_template.rtf',
    'delivery': 'delivery_template.rtf',
    'payment': 'payment_template.rtf'
}

with app.app_context():
    templates_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'templates')
    
    for doc_type, filename in template_files.items():
        file_path = os.path.join(templates_dir, filename)
        
        if os.path.exists(file_path):
            # Read new template content
            with open(file_path, 'r', encoding='utf-8') as f:
                new_content = f.read()
            
            # Update all templates of this type
            templates = DocumentTemplate.query.filter_by(
                document_type=doc_type,
                is_active=True
            ).all()
            
            print(f"\nUpdating {doc_type} templates:")
            for template in templates:
                print(f"  - {template.name} (ID: {template.id})")
                template.template_content = new_content
                template.template_file = filename
            
            if templates:
                print(f"  ✓ Updated {len(templates)} template(s)")
            else:
                print(f"  ! No active templates found for {doc_type}")
        else:
            print(f"  ✗ File not found: {file_path}")
    
    # Commit all changes
    db.session.commit()
    print("\n✓ All templates updated in database successfully!")
    
    # Verify
    print("\n" + "="*60)
    print("Template Summary:")
    print("="*60)
    all_templates = DocumentTemplate.query.filter_by(is_active=True).all()
    for template in all_templates:
        content_preview = template.template_content[:80] if template.template_content else "No content"
        print(f"\n{template.document_type.upper()}: {template.name}")
        print(f"  File: {template.template_file}")
        print(f"  Content: {content_preview}...")
