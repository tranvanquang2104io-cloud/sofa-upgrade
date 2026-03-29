import re
import os

routes_dir = r"Q:\Projects\sofa-flow\app\routes"
files_to_check = ['dashboard_routes.py', 'auth_routes.py', 'admin_routes.py']

def refactor_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Import t if not present
    if 'from app.utils.i18n import t' not in content:
        # Find where other app imports are, or just put it after 'from flask import ...'
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if line.startswith('from flask import '):
                lines.insert(i+1, 'from app.utils.i18n import t')
                break
        content = '\n'.join(lines)

    # Regex to find flash('some string', 'category')
    # \1 matches the first string literal (including quotes)
    # \2 matches the optional second parameter (including comma/quotes)
    
    # We only want to wrap the first argument. If it's an f-string f"...", we also wrap it.
    # Pattern: flash( (f?['"][^'"]*['"]) , ['"][^'"]*['"] )
    # Let's match anything up to the first comma or closing parenthesis for the first arg.
    # We will use a more robust regex or just simple replacements for common patterns.
    
    # flash('Some text', 'error') -> flash(t('Some text'), 'error')
    # flash(f'Error: {e}', 'error') -> flash(t(f'Error: {e}'), 'error')
    
    # Simple regex that matches flash(<arg1>, <arg2>) where arg1 is a string literal
    # Be careful not to wrap something already wrapped: flash(t('...'))
    
    pattern = re.compile(r"flash\(\s*(f?['\"].*?['\"])\s*(,\s*['\"].*?['\"])\s*\)")
    new_content = pattern.sub(r"flash(t(\1)\2)", content)
    
    # Case with no category: flash('Some text')
    pattern2 = re.compile(r"flash\(\s*(f?['\"].*?['\"])\s*\)")
    new_content = pattern2.sub(r"flash(t(\1))", new_content)
    
    if content != new_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Refactored: {filepath}")
    else:
        print(f"No changes needed: {filepath}")

for fname in files_to_check:
    fpath = os.path.join(routes_dir, fname)
    if os.path.exists(fpath):
        refactor_file(fpath)

