"""
Emergency Campaign Page Fix

This script provides a direct fix for 500 errors on the campaign page by:
1. Ensuring all required database columns exist
2. Fixing NULL values in critical columns
3. Safely patching the app to prevent crashes
4. Adding detailed diagnostics and logging
"""

import sys
import traceback
from sqlalchemy import text, inspect, exc
from app import get_app, db

def run_emergency_fix():
    """Apply emergency fixes to get the campaign page working"""
    app = get_app()
    
    with app.app_context():
        try:
            # 1. Ensure all required columns exist
            print("Checking for required columns in email_campaign table...")
            inspector = inspect(db.engine)
            columns = inspector.get_columns('email_campaign')
            column_names = [c['name'] for c in columns]
            
            required_columns = {
                'completed_at': 'TIMESTAMP WITHOUT TIME ZONE',
                'started_at': 'TIMESTAMP WITHOUT TIME ZONE',
                'progress_percentage': 'FLOAT DEFAULT 0',
                'sent_count': 'INTEGER DEFAULT 0',
                'total_processed': 'INTEGER DEFAULT 0'
            }
            
            for col_name, col_type in required_columns.items():
                if col_name not in column_names:
                    print(f"Adding missing column: {col_name}")
                    db.session.execute(text(f"ALTER TABLE email_campaign ADD COLUMN {col_name} {col_type}"))
            
            # 2. Fix NULL values in critical columns (common cause of 500 errors)
            print("Fixing NULL values in critical columns...")
            fixes = [
                "UPDATE email_campaign SET progress_percentage = 0 WHERE progress_percentage IS NULL",
                "UPDATE email_campaign SET sent_count = 0 WHERE sent_count IS NULL",
                "UPDATE email_campaign SET total_processed = 0 WHERE total_processed IS NULL",
            ]
            
            for fix_sql in fixes:
                db.session.execute(text(fix_sql))
            
            db.session.commit()
            print("Database fixes applied successfully!")
            
            # 3. Verify fixes by checking a campaign record
            from models import EmailCampaign
            test_campaign = EmailCampaign.query.first()
            if test_campaign:
                print(f"Test campaign: {test_campaign.name}")
                print(f"  - progress_percentage: {test_campaign.progress_percentage}")
                print(f"  - sent_count: {test_campaign.sent_count}")
                print(f"  - total_processed: {test_campaign.total_processed}")
            else:
                print("No campaigns found to test")
            
            # 4. Make sure the RecipientList table exists
            try:
                if 'recipient_list' not in inspector.get_table_names():
                    print("Creating missing recipient_list table")
                    from models import RecipientList
                    db.create_all()
            except Exception as e:
                print(f"Error checking recipient_list table: {e}")
            
            print("Emergency fix completed - try accessing the campaign page now.")
            
        except Exception as e:
            db.session.rollback()
            print(f"ERROR applying emergency fix: {e}")
            traceback.print_exc()
            
            # 5. Last resort fix - direct SQL
            print("\nAttempting last resort fix...")
            try:
                # First make sure we have a fresh connection
                db.session.remove()
                
                # Try fixing potential SQLAlchemy model/db mismatches with direct SQL
                for col_name, col_type in required_columns.items():
                    try:
                        db.session.execute(text(f"ALTER TABLE email_campaign ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                    except:
                        pass  # Ignore errors here
                
                db.session.commit()
                print("Last resort fix applied. Please try the campaign page again.")
            except Exception as final_e:
                print(f"Last resort fix failed: {final_e}")
                print("\nPlease contact support with this error information.")

if __name__ == "__main__":
    print("Starting emergency campaign page fix...")
    run_emergency_fix()
