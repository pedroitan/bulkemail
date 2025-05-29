"""
Translation compilation tool.

This script compiles the translation files (.po) into binary (.mo) files
that can be used by the application.
"""

import subprocess

def compile_translations():
    """Compile all translation files."""
    print("Compiling translations...")
    
    # Compile translations
    subprocess.run([
        'pybabel', 'compile',
        '-d', 'translations'
    ], check=True)
    
    print("Translations compiled successfully.")

if __name__ == '__main__':
    compile_translations()
