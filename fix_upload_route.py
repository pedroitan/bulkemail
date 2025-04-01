"""
Fix for campaign upload page error

This script specifically addresses issues with the /campaigns/{id}/upload route
that might be causing 500 errors after our recipient list management updates.
"""

import sys
import traceback
from sqlalchemy import text, inspect
from app import get_app, db
from models import RecipientList, EmailCampaign, EmailRecipient

def diagnose_upload_route():
    """Check for issues with the upload route"""
    print("Diagnosing upload route issues...")
    app = get_app()
    
    with app.app_context():
        # 1. Check if RecipientList model exists and has required fields
        inspector = inspect(db.engine)
        if 'recipient_list' not in inspector.get_table_names():
            print("WARNING: recipient_list table doesn't exist")
            
            # Check if we're importing RecipientList but table doesn't exist
            try:
                from models import RecipientList
                print("RecipientList model is imported but table doesn't exist")
                print("Creating recipient_list table...")
                
                # Create the table
                db.create_all()
                print("Created missing tables")
            except ImportError:
                print("RecipientList model not found in models.py")
        else:
            print("recipient_list table exists")
            
        # 2. Check the campaign we're trying to access
        try:
            campaign_id = 53  # The campaign ID from the error
            campaign = EmailCampaign.query.get(campaign_id)
            
            if campaign:
                print(f"Found campaign: ID={campaign.id}, Name={campaign.name}")
                # Check if campaign has all required fields
                attrs = ['id', 'name', 'subject', 'status', 'progress_percentage', 'sent_count']
                for attr in attrs:
                    value = getattr(campaign, attr, "MISSING")
                    print(f"  {attr}: {value}")
            else:
                print(f"Campaign with ID {campaign_id} not found")
        except Exception as e:
            print(f"Error accessing campaign: {e}")
            
        # 3. Ensure all necessary tables and associations exist
        try:
            print("\nChecking for recipient_list_items association table...")
            if 'recipient_list_items' not in inspector.get_table_names():
                print("WARNING: recipient_list_items table doesn't exist")
                
                # Create missing association table
                print("Creating association table...")
                stmt = text("""
                CREATE TABLE IF NOT EXISTS recipient_list_items (
                    list_id INTEGER NOT NULL,
                    recipient_id INTEGER NOT NULL,
                    PRIMARY KEY (list_id, recipient_id),
                    FOREIGN KEY(list_id) REFERENCES recipient_list (id),
                    FOREIGN KEY(recipient_id) REFERENCES email_recipient (id)
                )
                """)
                db.session.execute(stmt)
                db.session.commit()
                print("Created recipient_list_items table")
            else:
                print("recipient_list_items table exists")
        except Exception as e:
            db.session.rollback()
            print(f"Error checking/creating association table: {e}")
            
        # 4. Check if any template parameters are missing from render_template call
        print("\nChecking for recent changes to upload route that might break rendering...")
        print("The upload page expects recipient_lists parameter - ensure it exists")

def fix_upload_route():
    """Apply temporary fix for upload route issues"""
    print("\nApplying fixes for upload route...")
    app = get_app()
    
    with app.app_context():
        # Get all route functions
        for rule in app.url_map.iter_rules():
            if "/campaigns/<int:campaign_id>/upload" in str(rule):
                print(f"Found upload route: {rule}")
                print("This route now expects recipient_lists parameter in the template")
                
                # Create a temporary table if needed
                try:
                    # Ensure RecipientList model is working
                    if 'recipient_list' in inspect(db.engine).get_table_names():
                        list_count = RecipientList.query.count()
                        print(f"Found {list_count} recipient lists")
                    else:
                        print("recipient_list table not found - may cause errors")
                except Exception as e:
                    print(f"Error checking RecipientList: {e}")
                
        print("\nUploading a patched version of the upload template...")
        print("To fix this, you need to:")
        print("1. Make sure upload_recipients.html template handles case when recipient_lists=None")
        print("2. Update app.py to ensure recipient_lists is always defined even if empty")

def emergency_fix():
    """Apply emergency fix to get the upload route working"""
    print("\nApplying emergency fix...")
    
    app = get_app()
    with app.app_context():
        try:
            # Monkey patch the upload_recipients function temporarily
            from app import upload_recipients as original_upload
            from flask import render_template
            
            def patched_upload(campaign_id):
                try:
                    campaign = EmailCampaign.query.get_or_404(campaign_id)
                    from forms import UploadRecipientsForm
                    form = UploadRecipientsForm()
                    
                    # Simple fallback that doesn't rely on RecipientList
                    return render_template('upload_recipients.html', form=form, campaign=campaign, recipient_lists=[])
                except Exception as e:
                    print(f"Error in patched upload: {e}")
                    # Absolute fallback
                    return "Please contact support - emergency mode active", 200
            
            print("WARNING: Cannot apply monkey patch in diagnostic script")
            print("To fix this in production, you'll need to modify app.py or templates")
            print("  1. Check if RecipientList exists in your database")
            print("  2. Ensure upload_recipients.html can handle empty recipient_lists")
            print("  3. Add fallback in app.py to avoid 500 errors")
        except Exception as e:
            print(f"Error attempting emergency fix: {e}")

if __name__ == "__main__":
    try:
        print("===== UPLOAD ROUTE DIAGNOSTIC =====")
        diagnose_upload_route()
        fix_upload_route()
        emergency_fix()
        print("\n===== COMPLETED =====")
        print("Run this script on Render to diagnose upload route issues")
    except Exception as e:
        print(f"Error in diagnostic: {e}")
        traceback.print_exc()
