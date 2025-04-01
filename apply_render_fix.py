"""
Render Fix Applier

This script applies critical fixes to make the application work reliably on Render's free tier.
Run this directly on Render shell to fix:
1. Database connection issues
2. Campaign page 500 errors
3. Missing column issues

Usage: 
    cd /opt/render/project/src
    python apply_render_fix.py
"""

import sys
import traceback
from sqlalchemy import text, inspect, create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from flask import Flask
import os

def apply_fixes():
    print("Starting emergency fixes for Render deployment...")
    
    try:
        # First, ensure we have the proper Flask context
        from app import get_app, db
        app = get_app()
        
        with app.app_context():
            # 1. Fix database schema issues
            print("Checking database schema...")
            inspector = inspect(db.engine)
            
            # Check email_campaign table columns
            if 'email_campaign' in inspector.get_table_names():
                columns = inspector.get_columns('email_campaign')
                column_names = [c['name'] for c in columns]
                print(f"Found columns: {', '.join(column_names)}")
                
                # Define required columns
                required_columns = {
                    'completed_at': 'TIMESTAMP WITHOUT TIME ZONE',
                    'started_at': 'TIMESTAMP WITHOUT TIME ZONE',
                    'progress_percentage': 'FLOAT DEFAULT 0',
                    'sent_count': 'INTEGER DEFAULT 0',
                    'total_processed': 'INTEGER DEFAULT 0'
                }
                
                # Add missing columns
                missing_columns = []
                for col_name, col_type in required_columns.items():
                    if col_name not in column_names:
                        missing_columns.append(col_name)
                        print(f"Adding missing column: {col_name}")
                        db.session.execute(text(f"ALTER TABLE email_campaign ADD COLUMN {col_name} {col_type}"))
                
                if missing_columns:
                    print(f"Added missing columns: {', '.join(missing_columns)}")
                else:
                    print("All required columns exist")
                
                # 2. Fix NULL values - critical for preventing 500 errors
                print("\nFixing NULL values in critical columns...")
                fixes = [
                    "UPDATE email_campaign SET progress_percentage = 0 WHERE progress_percentage IS NULL",
                    "UPDATE email_campaign SET sent_count = 0 WHERE sent_count IS NULL",
                    "UPDATE email_campaign SET total_processed = 0 WHERE total_processed IS NULL",
                ]
                
                for fix_sql in fixes:
                    result = db.session.execute(text(fix_sql))
                    print(f"Applied fix: {fix_sql} (affected rows: {result.rowcount})")
                
                db.session.commit()
                
                # 3. Optimize database connection pooling
                print("\nOptimizing database connection pooling...")
                engine = db.engine
                engine.pool._pool.maxsize = 5  # Set smaller pool size
                engine.pool._pool.timeout = 30  # Set shorter timeout
                print("Applied connection pool optimizations")
                
                # 4. Verify fixes by accessing a campaign
                print("\nVerifying fixes by accessing campaign data...")
                from models import EmailCampaign
                try:
                    campaign = EmailCampaign.query.first()
                    if campaign:
                        print(f"Successfully accessed campaign: {campaign.name}")
                        print(f"  Status: {campaign.status}")
                        print(f"  Progress: {campaign.progress_percentage}%")
                        print(f"  Sent count: {campaign.sent_count}")
                        print(f"  Total processed: {campaign.total_processed}")
                    else:
                        print("No campaigns found to verify")
                except Exception as e:
                    print(f"Error verifying campaign access: {str(e)}")
                
                # 5. Ensure recipient_list table exists for upload page
                if 'recipient_list' not in inspector.get_table_names():
                    print("\nCreating missing recipient_list table...")
                    db.session.execute(text("""
                    CREATE TABLE IF NOT EXISTS recipient_list (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        description TEXT,
                        active_recipients INTEGER DEFAULT 0,
                        total_recipients INTEGER DEFAULT 0,
                        created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
                    )"""))
                    
                    print("Creating recipient_list_items association table...")
                    db.session.execute(text("""
                    CREATE TABLE IF NOT EXISTS recipient_list_items (
                        list_id INTEGER NOT NULL,
                        recipient_id INTEGER NOT NULL,
                        PRIMARY KEY (list_id, recipient_id),
                        FOREIGN KEY(list_id) REFERENCES recipient_list (id),
                        FOREIGN KEY(recipient_id) REFERENCES email_recipient (id)
                    )"""))
                    
                    db.session.commit()
                    print("Created missing tables")
                else:
                    print("\nRecipient list tables exist")
                
                print("\nAll fixes applied successfully!")
                print("Try accessing your campaign pages now - they should work correctly.")
            else:
                print("ERROR: email_campaign table not found")
    
    except Exception as e:
        print(f"\nERROR applying fixes: {str(e)}")
        traceback.print_exc()
        print("\nTrying last resort fix...")
        
        # Last resort - direct database connection
        try:
            # Get database URL from environment or config
            database_url = os.environ.get('DATABASE_URL')
            if not database_url:
                from config import Config
                database_url = Config.SQLALCHEMY_DATABASE_URI
            
            print(f"Connecting directly to database...")
            engine = create_engine(database_url)
            Session = scoped_session(sessionmaker(bind=engine))
            session = Session()
            
            # Apply fixes directly
            fixes = [
                "ALTER TABLE email_campaign ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP WITHOUT TIME ZONE",
                "ALTER TABLE email_campaign ADD COLUMN IF NOT EXISTS started_at TIMESTAMP WITHOUT TIME ZONE",
                "ALTER TABLE email_campaign ADD COLUMN IF NOT EXISTS progress_percentage FLOAT DEFAULT 0",
                "ALTER TABLE email_campaign ADD COLUMN IF NOT EXISTS sent_count INTEGER DEFAULT 0", 
                "ALTER TABLE email_campaign ADD COLUMN IF NOT EXISTS total_processed INTEGER DEFAULT 0",
                "UPDATE email_campaign SET progress_percentage = 0 WHERE progress_percentage IS NULL",
                "UPDATE email_campaign SET sent_count = 0 WHERE sent_count IS NULL",
                "UPDATE email_campaign SET total_processed = 0 WHERE total_processed IS NULL"
            ]
            
            for fix in fixes:
                try:
                    session.execute(text(fix))
                    print(f"Applied: {fix}")
                except Exception as fix_error:
                    print(f"Error applying {fix}: {str(fix_error)}")
            
            session.commit()
            print("Last resort fixes applied")
        except Exception as last_error:
            print(f"Last resort fix failed: {str(last_error)}")
            print("\nPlease contact support with these error details")

if __name__ == "__main__":
    print("=" * 50)
    print("RENDER DEPLOYMENT FIX TOOL")
    print("=" * 50)
    apply_fixes()
    print("=" * 50)
