"""
EmailRecipient Table Fix Script

This script fixes the email_recipient table by adding the missing global_status column
and other required columns needed for bounce and complaint handling.
"""

import sys
import traceback
from sqlalchemy import text, inspect
from app import get_app, db

def fix_recipient_table():
    """Add missing columns to email_recipient table"""
    print("Starting EmailRecipient table fix...")
    
    app = get_app()
    with app.app_context():
        try:
            # Check if email_recipient table exists
            inspector = inspect(db.engine)
            if 'email_recipient' not in inspector.get_table_names():
                print("ERROR: email_recipient table not found!")
                return
                
            # Get current columns
            columns = inspector.get_columns('email_recipient')
            column_names = [c['name'] for c in columns]
            print(f"Found {len(columns)} columns in email_recipient table")
            
            # Define columns that should exist
            required_columns = {
                'global_status': "VARCHAR(20) DEFAULT 'active'",
                'is_verified': "BOOLEAN DEFAULT false",
                'verification_result': "TEXT DEFAULT NULL",
                'verification_date': "TIMESTAMP WITHOUT TIME ZONE DEFAULT NULL",
                'last_opened_at': "TIMESTAMP WITHOUT TIME ZONE DEFAULT NULL",
                'open_count': "INTEGER DEFAULT 0",
                'last_clicked_at': "TIMESTAMP WITHOUT TIME ZONE DEFAULT NULL",
                'click_count': "INTEGER DEFAULT 0"
            }
            
            # Add missing columns
            missing = []
            for col_name, col_type in required_columns.items():
                if col_name not in column_names:
                    missing.append(col_name)
                    print(f"Adding missing column: {col_name}")
                    db.session.execute(text(f"ALTER TABLE email_recipient ADD COLUMN {col_name} {col_type}"))
            
            if missing:
                db.session.commit()
                print(f"Added {len(missing)} missing columns to email_recipient table: {', '.join(missing)}")
            else:
                print("No missing columns to add.")
                
            # Set default global_status for existing records if needed
            if 'global_status' in missing:
                print("Setting default global_status for existing records...")
                db.session.execute(text("UPDATE email_recipient SET global_status = 'active' WHERE global_status IS NULL"))
                db.session.commit()
                print("Default global_status set successfully")
                
            # Verify fix
            from models import EmailRecipient
            test_recipient = EmailRecipient.query.first()
            if test_recipient:
                print(f"Fix verified - Successfully accessed test recipient: {test_recipient.email}")
                print(f"  global_status: {test_recipient.global_status}")
            else:
                print("No recipients found to verify fix")
                
            print("EmailRecipient table fix completed successfully!")
            
        except Exception as e:
            db.session.rollback()
            print(f"ERROR: {str(e)}")
            traceback.print_exc()
            
            # Last resort direct SQL fix
            print("\nAttempting direct SQL fix...")
            try:
                # Ensure we have a fresh connection
                db.session.remove()
                
                # Try adding the column with direct SQL that's most likely to succeed
                db.session.execute(text("ALTER TABLE email_recipient ADD COLUMN IF NOT EXISTS global_status VARCHAR(20) DEFAULT 'active'"))
                db.session.commit()
                print("Added global_status column with direct SQL")
            except Exception as sql_error:
                print(f"Direct SQL fix failed: {str(sql_error)}")
                print("Please run this script on Render directly to fix the issue")

if __name__ == "__main__":
    fix_recipient_table()
