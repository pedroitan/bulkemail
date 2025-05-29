#!/usr/bin/env python3
"""
Script to create a temporary deployable version of the application
that works without the missing columns but includes a schema updater route.

This allows:
1. The application to deploy successfully without the columns
2. A route to add the columns once deployed
3. A way to switch back to the main branch later
"""

import os
import re
import sys
import subprocess

def modify_models_py():
    """Comment out new columns in models.py"""
    print("Modifying models.py...")
    with open('models.py', 'r') as f:
        content = f.read()
    
    # Comment out the new columns
    modified = re.sub(
        r'(^\s*total_recipients\s*=.*$)',
        r'    # TEMP_DISABLED: \1',
        content,
        flags=re.MULTILINE
    )
    
    modified = re.sub(
        r'(^\s*last_segment_position\s*=.*$)',
        r'    # TEMP_DISABLED: \1',
        modified,
        flags=re.MULTILINE
    )
    
    modified = re.sub(
        r'(^\s*next_segment_time\s*=.*$)',
        r'    # TEMP_DISABLED: \1',
        modified,
        flags=re.MULTILINE
    )
    
    with open('models.py', 'w') as f:
        f.write(modified)

def modify_scheduler_py():
    """Modify scheduler.py to remove references to the missing columns"""
    print("Modifying scheduler.py...")
    with open('scheduler.py', 'r') as f:
        content = f.read()
    
    # Replace references to campaign.total_recipients
    modified = re.sub(
        r'campaign\.total_recipients',
        'len(recipient_ids) if "recipient_ids" in locals() else 0',
        content
    )
    
    # Replace references to campaign.last_segment_position
    modified = re.sub(
        r'campaign\.last_segment_position\s*=',
        '# TEMP_DISABLED: campaign.last_segment_position =',
        modified
    )
    
    # Replace references to campaign.next_segment_time
    modified = re.sub(
        r'campaign\.next_segment_time\s*=',
        '# TEMP_DISABLED: campaign.next_segment_time =',
        modified
    )
    
    with open('scheduler.py', 'w') as f:
        f.write(modified)

def add_schema_update_route():
    """Add a route to app.py to update the schema once deployed"""
    print("Adding schema update route to app.py...")
    with open('app.py', 'r') as f:
        content = f.read()
    
    # Add sqlalchemy text import if needed
    if 'from sqlalchemy import text' not in content:
        content = re.sub(
            r'from datetime import datetime, timedelta',
            'from datetime import datetime, timedelta\nfrom sqlalchemy import text',
            content
        )
    
    # Check if the route already exists
    if '@app.route(\'/admin/fix-schema\')' in content:
        print("Schema update route already exists")
        return
    
    # Add the schema update route
    schema_route = """
@app.route('/admin/fix-schema')
def fix_database_schema():
    \"\"\"Add missing columns to the email_campaign table\"\"\"
    try:
        # Connect to the database
        with db.engine.connect() as conn:
            # Check which columns already exist
            columns_result = conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'email_campaign'"
            ))
            existing_columns = [row[0] for row in columns_result]
            
            # Track which columns we've added
            added_columns = []
            
            # Add missing columns if they don't exist
            if 'total_recipients' not in existing_columns:
                conn.execute(text("ALTER TABLE email_campaign ADD COLUMN total_recipients INTEGER DEFAULT 0"))
                added_columns.append('total_recipients')
            
            if 'last_segment_position' not in existing_columns:
                conn.execute(text("ALTER TABLE email_campaign ADD COLUMN last_segment_position INTEGER DEFAULT 0"))
                added_columns.append('last_segment_position')
            
            if 'next_segment_time' not in existing_columns:
                conn.execute(text("ALTER TABLE email_campaign ADD COLUMN next_segment_time TIMESTAMP"))
                added_columns.append('next_segment_time')
            
            # Commit the transaction
            trans = conn.begin()
            trans.commit()
            
        return f\"\"\"
        <html>
            <head><title>Schema Update Complete</title></head>
            <body>
                <h1>Database Schema Update</h1>
                <p>The following columns were added to the email_campaign table:</p>
                <ul>
                    {''.join(f'<li>{col}</li>' for col in added_columns)}
                </ul>
                <p>If no columns are listed, they may already exist in the table.</p>
                <p><a href="/">Return to homepage</a></p>
            </body>
        </html>
        \"\"\"
    except Exception as e:
        return f\"\"\"
        <html>
            <head><title>Schema Update Error</title></head>
            <body>
                <h1>Error Updating Schema</h1>
                <p>An error occurred while updating the database schema:</p>
                <pre>{str(e)}</pre>
                <p><a href="/">Return to homepage</a></p>
            </body>
        </html>
        \"\"\"
"""
    
    # Find a good place to add the route - before the last route
    last_route_match = re.search(r'@app\.route\([^)]+\)[^\n]*\n[^\n]*\n.*$', content, re.DOTALL)
    if last_route_match:
        insert_pos = last_route_match.start()
        content = content[:insert_pos] + schema_route + content[insert_pos:]
    else:
        # Fallback - add at the end
        content += schema_route
    
    with open('app.py', 'w') as f:
        f.write(content)

def create_instructions():
    """Create instructions file for how to use this temporary fix"""
    print("Creating instructions file...")
    with open('TEMP_FIX_INSTRUCTIONS.md', 'w') as f:
        f.write("""# Temporary Fix Instructions

## What This Fix Does

This is a temporary fix to allow the application to deploy without the missing columns in the database.
Once deployed, you can add the missing columns through a special admin route.

## How to Use

1. **Deploy this branch to Render**:
   - In the Render dashboard, update your service to use branch `temp-deploy-fix`
   - This version should deploy successfully

2. **Run the Schema Update**:
   - Once deployed, visit: `https://your-app-url.onrender.com/admin/fix-schema`
   - This will add the missing columns to your database
   - You'll see a confirmation page showing which columns were added

3. **Switch Back to Main Branch**:
   - After the schema is fixed, go to the Render dashboard
   - Update your service to use the `main` branch again
   - The deployment should now succeed because the columns exist in the database

## Technical Details

This temporary fix:
1. Comments out the column definitions in `models.py`
2. Modifies code in `scheduler.py` to work without these columns
3. Adds a special route in `app.py` to update the database schema

Once the database schema is fixed, you can switch back to the main branch with all features enabled.
""")

def main():
    """Main function to apply all modifications"""
    # Check if we're in the right directory
    if not os.path.exists('models.py') or not os.path.exists('scheduler.py'):
        print("Error: This script must be run from the project root directory")
        return 1
    
    print("Creating temporary fix to make application deployable...")
    
    # Apply all modifications
    modify_models_py()
    modify_scheduler_py()
    add_schema_update_route()
    create_instructions()
    
    # Commit changes
    subprocess.run(['git', 'add', 'models.py', 'scheduler.py', 'app.py', 'TEMP_FIX_INSTRUCTIONS.md'])
    subprocess.run(['git', 'commit', '-m', 'Temporary fix to allow deployment without new columns'])
    
    print("\nTemporary fix created successfully!")
    print("Next steps:")
    print("1. Push this branch to GitHub: git push -u origin temp-deploy-fix")
    print("2. Deploy this branch on Render")
    print("3. Visit /admin/fix-schema on your deployed app to add the missing columns")
    print("4. Switch back to the main branch in Render")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
