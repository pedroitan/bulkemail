"""
Translation extraction tool.

This script extracts all translatable strings from the application
and updates the translation files.
"""

import os
import subprocess
import sys

def extract_translations():
    """Extract translatable strings and update translation files."""
    print("Extracting messages...")
    
    # Extract messages from Python and Jinja2 templates
    subprocess.run([
        'pybabel', 'extract', 
        '-F', 'babel.cfg',
        '-o', 'messages.pot',
        '.'
    ], check=True)
    
    # Check if Brazilian Portuguese translation exists
    if not os.path.exists('translations/pt_BR/LC_MESSAGES/messages.po'):
        print("Initializing Brazilian Portuguese translation...")
        subprocess.run([
            'pybabel', 'init',
            '-i', 'messages.pot',
            '-d', 'translations',
            '-l', 'pt_BR'
        ], check=True)
    else:
        print("Updating Brazilian Portuguese translation...")
        subprocess.run([
            'pybabel', 'update',
            '-i', 'messages.pot',
            '-d', 'translations',
            '-l', 'pt_BR'
        ], check=True)
    
    print("Translations extracted. Edit the .po files in translations directory.")
    print("After editing, compile translations with: python compile_translations.py")

if __name__ == '__main__':
    extract_translations()
