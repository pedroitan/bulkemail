"""
Campaign Page Diagnostic Script

This script helps diagnose 500 errors on the campaign page by:
1. Checking for NULL values in critical columns
2. Verifying all required columns exist
3. Testing the campaign queries that might be failing
4. Adding diagnostic logging
"""

import os
import sys
import traceback
from sqlalchemy import text, inspect
from app import get_app, db
from models import EmailCampaign, EmailRecipient

def inspect_table_columns():
    """Inspect the email_campaign table schema"""
    print("=== EMAIL_CAMPAIGN TABLE INSPECTION ===")
    app = get_app()
    
    with app.app_context():
        # Get table inspector
        inspector = inspect(db.engine)
        
        # Check if the table exists
        if 'email_campaign' not in inspector.get_table_names():
            print("ERROR: email_campaign table doesn't exist!")
            return
            
        # Get columns
        columns = inspector.get_columns('email_campaign')
        print(f"Found {len(columns)} columns in email_campaign table:")
        
        for column in columns:
            print(f"  - {column['name']} ({column['type']})")
        
        # Check for required columns
        required_columns = [
            'id', 'name', 'subject', 'body_html', 'body_text', 
            'sender_name', 'sender_email', 'status',
            'completed_at', 'started_at', 'progress_percentage',
            'sent_count', 'total_processed'
        ]
        
        existing_column_names = [col['name'] for col in columns]
        
        for req_col in required_columns:
            if req_col not in existing_column_names:
                print(f"MISSING COLUMN: {req_col}")
            else:
                print(f"FOUND REQUIRED COLUMN: {req_col}")

def check_campaign_queries():
    """Test all queries used on the campaign page"""
    print("\n=== TESTING CAMPAIGN QUERIES ===")
    app = get_app()
    
    with app.app_context():
        # Try the main campaigns query
        try:
            print("Testing main campaigns list query...")
            campaigns = EmailCampaign.query.order_by(EmailCampaign.created_at.desc()).all()
            print(f"Success! Found {len(campaigns)} campaigns")
            
            # Check for NULL values in critical columns
            for campaign in campaigns:
                print(f"\nCampaign ID: {campaign.id}, Name: {campaign.name}")
                print(f"  Status: {campaign.status}")
                print(f"  Progress: {campaign.progress_percentage}%")
                print(f"  Sent: {campaign.sent_count}")
                print(f"  Total: {campaign.total_processed}")
                print(f"  Started: {campaign.started_at}")
                print(f"  Completed: {campaign.completed_at}")
                
                # Test recipient count query for each campaign
                try:
                    recipient_count = EmailRecipient.query.filter_by(campaign_id=campaign.id).count()
                    print(f"  Recipients: {recipient_count}")
                except Exception as e:
                    print(f"  ERROR counting recipients: {str(e)}")
        
        except Exception as e:
            print(f"ERROR in campaigns query: {str(e)}")
            traceback.print_exc()

def test_campaign_detail_view():
    """Test the campaign detail view query"""
    print("\n=== TESTING CAMPAIGN DETAIL VIEW ===")
    app = get_app()
    
    with app.app_context():
        # Get the first campaign
        try:
            campaign = EmailCampaign.query.first()
            if not campaign:
                print("No campaigns found to test")
                return
                
            print(f"Testing detail view for campaign ID: {campaign.id}")
            
            # Try to access all attributes used in the detail template
            attributes = [
                'id', 'name', 'subject', 'status', 'sender_name', 
                'sender_email', 'scheduled_time', 'created_at', 
                'started_at', 'completed_at', 'progress_percentage'
            ]
            
            for attr in attributes:
                try:
                    value = getattr(campaign, attr)
                    print(f"  {attr}: {value}")
                except AttributeError:
                    print(f"  ERROR: Missing attribute '{attr}'")
            
            # Test recipient query
            try:
                recipients = EmailRecipient.query.filter_by(campaign_id=campaign.id).limit(5).all()
                print(f"  Found {len(recipients)} recipients (showing first 5)")
                
                if recipients:
                    print("  Testing recipient attributes...")
                    for recipient in recipients:
                        # Check recipient attributes
                        print(f"    Email: {recipient.email}")
                        print(f"    Status: {recipient.status}")
            except Exception as e:
                print(f"  ERROR querying recipients: {str(e)}")
                
        except Exception as e:
            print(f"ERROR in campaign detail query: {str(e)}")
            traceback.print_exc()

def fix_null_values():
    """Fix any NULL values in the critical columns"""
    print("\n=== FIXING NULL VALUES ===")
    app = get_app()
    
    with app.app_context():
        try:
            # Set default values for nullable columns
            update_sql = text("""
                UPDATE email_campaign 
                SET 
                    progress_percentage = 0 WHERE progress_percentage IS NULL,
                    sent_count = 0 WHERE sent_count IS NULL,
                    total_processed = 0 WHERE total_processed IS NULL
            """)
            
            db.session.execute(update_sql)
            db.session.commit()
            print("Fixed NULL values in progress tracking columns")
        except Exception as e:
            db.session.rollback()
            print(f"ERROR fixing NULL values: {str(e)}")

def fix_missing_methods():
    """Add any missing methods to models dynamically"""
    print("\n=== CHECKING FOR MISSING METHODS ===")
    app = get_app()
    
    with app.app_context():
        # Check for important methods
        campaign = EmailCampaign.query.first()
        if campaign:
            # Ensure get_progress method exists
            if not hasattr(campaign, 'get_progress') or not callable(getattr(campaign, 'get_progress', None)):
                print("Adding get_progress method to EmailCampaign")
                # Add the method dynamically
                def get_progress(self):
                    if not self.total_processed or self.total_processed == 0:
                        return 0
                    return min(100, round((self.sent_count / self.total_processed) * 100, 1))
                
                EmailCampaign.get_progress = get_progress
            else:
                print("get_progress method exists")

if __name__ == "__main__":
    print("Starting campaign page diagnostics...")
    
    try:
        # Run all diagnostic functions
        inspect_table_columns()
        check_campaign_queries()
        test_campaign_detail_view()
        fix_null_values()
        fix_missing_methods()
        
        print("\n=== DIAGNOSTICS COMPLETE ===")
        print("If you're still seeing errors, check application logs for more details.")
        print("You can run this script directly on the Render shell to diagnose issues.")
    except Exception as e:
        print(f"ERROR in diagnostics: {str(e)}")
        traceback.print_exc()
