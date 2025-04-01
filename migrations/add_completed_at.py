"""
Database migration script to add the completed_at column to the email_campaign table.

This script should be run on the production database to fix the 
'column email_campaign.completed_at does not exist' error.

Usage:
python migrations/add_completed_at.py
"""

import os
import sys
from datetime import datetime

# Add the parent directory to the path so we can import our application modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import required modules
from app import get_app, db
from sqlalchemy import text

def run_migration():
    """
    Add the completed_at column to the email_campaign table if it doesn't exist
    """
    print("Starting migration: Add completed_at column to email_campaign table")
    
    # Get the Flask app to ensure we have the proper database context
    app = get_app()
    
    with app.app_context():
        # Check if the column already exists to avoid errors on rerun
        check_column_sql = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'email_campaign' 
            AND column_name = 'completed_at';
        """)
        
        result = db.session.execute(check_column_sql)
        column_exists = result.fetchone() is not None
        
        if column_exists:
            print("Column 'completed_at' already exists. Skipping migration.")
            return
        
        # Add the column
        add_column_sql = text("""
            ALTER TABLE email_campaign 
            ADD COLUMN completed_at TIMESTAMP WITHOUT TIME ZONE;
        """)
        
        try:
            # Execute the SQL
            db.session.execute(add_column_sql)
            db.session.commit()
            
            print("Migration completed successfully: Added 'completed_at' column to email_campaign table")
        except Exception as e:
            db.session.rollback()
            print(f"Error during migration: {str(e)}")
            sys.exit(1)

if __name__ == "__main__":
    run_migration()
