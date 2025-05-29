#!/usr/bin/env python
"""
Manual test for email tracking functionality.
This simulates someone opening an email by directly accessing the tracking pixel.
"""

import os
import sys
import requests
from datetime import datetime

# Set up proper environment for Flask app
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
os.environ["FLASK_ENV"] = "development"

# Import the Flask application
from app import app, db
from models import EmailCampaign, EmailRecipient, EmailTracking, EmailTrackingEvent

def test_manual_tracking_open():
    """Manually simulate email opens by accessing the tracking pixel URL"""
    with app.app_context():
        # Find the campaign and recipient to test
        campaign = EmailCampaign.query.filter_by(status='sent').first() or \
                  EmailCampaign.query.first()
        
        if not campaign:
            print("❌ No campaigns found to test!")
            return False
            
        print(f"Using campaign: {campaign.id} - {campaign.name}")
        
        # Find a recipient for this campaign
        recipient = EmailRecipient.query.filter_by(campaign_id=campaign.id).first()
        
        if not recipient:
            print("❌ No recipients found for this campaign!")
            return False
            
        print(f"Using recipient: {recipient.id} - {recipient.email}")
        
        # Print current open count
        print(f"Current open count: {recipient.open_count or 0}")
        print(f"Last opened at: {recipient.last_opened_at}")
        
        # Find tracking records for this recipient
        tracking_records = EmailTracking.query.filter_by(
            email_id=campaign.id,
            recipient_id=recipient.id,
            tracking_type='open'
        ).all()
        
        if not tracking_records:
            print("❌ No tracking records found for this recipient!")
            
            # Create a new tracking record
            from email_tracking import EmailTrackingManager
            tracking_manager = app.tracking_manager
            
            if not tracking_manager:
                print("❌ Tracking manager not initialized!")
                return False
                
            print("Creating a new tracking pixel...")
            tracking_url = tracking_manager.generate_tracking_pixel(
                campaign.id, recipient.id
            )
            tracking_id = tracking_url.split('/')[-1].split('.')[0]
        else:
            # Use the first tracking record
            print(f"Found {len(tracking_records)} tracking records")
            tracking_id = tracking_records[0].tracking_id
        
        print(f"Using tracking ID: {tracking_id}")
        
        # Construct the tracking pixel URL
        tracking_url = f"http://localhost:5000/tracking/pixel/{tracking_id}.png"
        print(f"Tracking URL: {tracking_url}")
        
        # Manual option: Open URL in browser
        print("\nTo test manually, open this URL in your browser:")
        print(tracking_url)
        
        # Simulate opening the email by accessing the tracking pixel
        try:
            print("\nSimulating email open by accessing the tracking pixel...")
            response = requests.get(tracking_url)
            print(f"Response status code: {response.status_code}")
            
            if response.status_code == 200:
                print("✅ Successfully accessed tracking pixel!")
            else:
                print(f"❌ Failed to access tracking pixel: {response.text}")
                return False
                
            # Check if the open was recorded
            # Need to refresh the recipient from the database
            recipient = EmailRecipient.query.get(recipient.id)
            print(f"New open count: {recipient.open_count or 0}")
            print(f"Last opened at: {recipient.last_opened_at}")
            
            if recipient.open_count and recipient.open_count > 0:
                print("✅ Open was recorded in the database!")
                return True
            else:
                print("❌ Open was NOT recorded in the database!")
                return False
                
        except Exception as e:
            print(f"❌ Error during testing: {str(e)}")
            return False

if __name__ == "__main__":
    try:
        with app.app_context():
            success = test_manual_tracking_open()
            if success:
                print("\n✅ Email open tracking test completed successfully!")
            else:
                print("\n❌ Email open tracking test failed!")
    except Exception as e:
        print(f"\n❌ Error during testing: {str(e)}")
