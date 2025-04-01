"""
Database migration script to add progress tracking columns to the email_campaign table.

This script adds all columns needed for tracking campaign progress:
- started_at: When the campaign started sending
- completed_at: When the campaign finished sending
- sent_count: How many emails have been sent
- total_processed: Total number of emails processed (including failed attempts)
- progress_percentage: Percentage of completion

Usage:
python migrations/add_progress_tracking_columns.py
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
    Add all progress tracking columns to the email_campaign table if they don't exist
    """
    print("Starting migration: Add progress tracking columns to email_campaign table")
    
    # Get the Flask app to ensure we have the proper database context
    app = get_app()
    
    with app.app_context():
        # Columns to check and add
        columns = [
            {"name": "started_at", "type": "TIMESTAMP WITHOUT TIME ZONE"},
            {"name": "completed_at", "type": "TIMESTAMP WITHOUT TIME ZONE"},
            {"name": "sent_count", "type": "INTEGER", "default": "0"},
            {"name": "total_processed", "type": "INTEGER", "default": "0"},
            {"name": "progress_percentage", "type": "FLOAT", "default": "0.0"}
        ]
        
        # Check which columns already exist
        existing_columns = []
        for column in columns:
            check_column_sql = text(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'email_campaign' 
                AND column_name = '{column["name"]}';
            """)
            
            result = db.session.execute(check_column_sql)
            if result.fetchone() is not None:
                existing_columns.append(column["name"])
        
        # Add missing columns
        try:
            for column in columns:
                if column["name"] not in existing_columns:
                    default_clause = f"DEFAULT {column['default']}" if "default" in column else ""
                    add_column_sql = text(f"""
                        ALTER TABLE email_campaign 
                        ADD COLUMN {column["name"]} {column["type"]} {default_clause};
                    """)
                    
                    db.session.execute(add_column_sql)
                    print(f"Added column: {column['name']}")
            
            db.session.commit()
            print("Migration completed successfully")
        except Exception as e:
            db.session.rollback()
            print(f"Error during migration: {str(e)}")
            sys.exit(1)

if __name__ == "__main__":
    run_migration()
