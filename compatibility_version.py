#!/usr/bin/env python
"""
Script to create a compatibility version that will deploy on Render
by temporarily removing references to the new columns.

Run this script locally to create a branch that Render can deploy,
then use that deployment to fix the database schema.
"""

import os
import re
import sys
import subprocess

def modify_models_py():
    """Modify models.py to remove new columns"""
    with open('models.py', 'r') as f:
        content = f.read()
    
    # Comment out the new columns
    modified = re.sub(
        r'(^\s*total_recipients\s*=.*$)',
        r'    # TEMP DISABLED FOR COMPATIBILITY: \1',
        content,
        flags=re.MULTILINE
    )
    
    modified = re.sub(
        r'(^\s*last_segment_position\s*=.*$)',
        r'    # TEMP DISABLED FOR COMPATIBILITY: \1',
        modified,
        flags=re.MULTILINE
    )
    
    modified = re.sub(
        r'(^\s*next_segment_time\s*=.*$)',
        r'    # TEMP DISABLED FOR COMPATIBILITY: \1',
        modified,
        flags=re.MULTILINE
    )
    
    with open('models.py', 'w') as f:
        f.write(modified)
        
    print("Modified models.py to comment out new columns")

def modify_scheduler_py():
    """Modify scheduler.py to remove references to new columns"""
    with open('scheduler.py', 'r') as f:
        content = f.read()
        
    # Comment out usage of the new columns
    patterns = [
        r'total_recipients\s*=',
        r'last_segment_position\s*=',
        r'next_segment_time\s*='
    ]
    
    for pattern in patterns:
        content = re.sub(
            pattern,
            '# TEMP DISABLED: \g<0>',
            content
        )
        
    with open('scheduler.py', 'w') as f:
        f.write(content)
        
    print("Modified scheduler.py to comment out new column references")

def create_database_update_route():
    """Add an admin route to app.py that will update the database schema"""
    with open('app.py', 'r') as f:
        content = f.read()
    
    # Check if route already exists
    if 'def admin_update_schema' in content:
        print("Admin route already exists, skipping")
        return
    
    # Find a good place to add our new route (after direct_test)
    route_code = """
    @app.route('/admin/update-schema')
    def admin_update_schema():
        \"\"\"Temporary admin route to update the database schema with missing columns\"\"\"
        try:
            # Manually run SQL to add the missing columns
            with db.engine.connect() as connection:
                # Add missing columns
                connection.execute(text("ALTER TABLE email_campaign ADD COLUMN IF NOT EXISTS total_recipients INTEGER DEFAULT 0"))
                connection.execute(text("ALTER TABLE email_campaign ADD COLUMN IF NOT EXISTS last_segment_position INTEGER DEFAULT 0"))
                connection.execute(text("ALTER TABLE email_campaign ADD COLUMN IF NOT EXISTS next_segment_time TIMESTAMP"))
                
            # Return a simple HTML response
            return "<h1>Database Schema Update</h1><p>Added missing columns to the email_campaign table.</p><p><a href='/'>Return to home</a></p>"
        except Exception as e:
            return f"<h1>Error</h1><p>An error occurred: {str(e)}</p>"
    """
    
    # Add import for text if needed
    if 'from sqlalchemy import' in content:
        if 'text' not in content:
            content = re.sub(
                r'from sqlalchemy import ([^,\n]+)',
                r'from sqlalchemy import \1, text',
                content
            )
    else:
        # Add the import
        content = re.sub(
            r'(from datetime import .*)',
            r'\1\nfrom sqlalchemy import text',
            content
        )
    
    # Add the route after direct_test
    content = re.sub(
        r'(\s+@app\.route\(\'/direct-test\'\)[^\n]*\n[^\n]*\n[^\n]*\n[^\n]*\n)',
        r'\1' + route_code,
        content
    )
    
    with open('app.py', 'w') as f:
        f.write(content)
        
    print("Added admin route to app.py for database schema updates")

def create_compatibility_branch():
    """Create a Git branch for the compatibility version"""
    # Create a new branch
    branch_name = f"compatibility-version-{int(os.path.getmtime('models.py'))}"
    
    subprocess.run(['git', 'checkout', '-b', branch_name])
    print(f"Created branch: {branch_name}")
    
    # Apply the modifications
    modify_models_py()
    modify_scheduler_py()
    create_database_update_route()
    
    # Commit the changes
    subprocess.run(['git', 'add', 'models.py', 'scheduler.py', 'app.py'])
    subprocess.run(['git', 'commit', '-m', 'Temporary compatibility version for deployment'])
    
    # Push the branch
    subprocess.run(['git', 'push', '-u', 'origin', branch_name])
    
    print(f"\nCompatibility branch {branch_name} created and pushed!")
    print("Instructions:")
    print("1. Go to Render dashboard and deploy this branch")
    print("2. After deployment, visit /admin/update-schema to update the database")
    print("3. Then switch back to the main branch in Render")
    
if __name__ == "__main__":
    # Check if we're in the right directory
    if not os.path.exists('models.py') or not os.path.exists('scheduler.py'):
        print("Error: Run this script from the project root directory")
        sys.exit(1)
        
    # Create the compatibility branch
    create_compatibility_branch()
