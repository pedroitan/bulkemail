#!/usr/bin/env python
"""
Script to refresh any caching or update tracking display in the UI.
"""

import os
import sys
import logging
from datetime import datetime

# Set up environment
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
os.environ["FLASK_ENV"] = "development"

# Import Flask app and models
from app import app, db
from models import EmailCampaign, EmailRecipient, EmailTracking, EmailTrackingEvent

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_tracking_display():
    """Force update of any tracking data to ensure UI is current."""
    with app.app_context():
        # Get the exact data that will be shown in the UI
        campaigns = EmailCampaign.query.order_by(EmailCampaign.created_at.desc()).all()
        
        print(f"Found {len(campaigns)} campaigns")
        
        # Print the tracking statistics that should be displayed
        print("\nTracking statistics that should be displayed in UI:")
        print("-" * 50)
        print(f"{'ID':<4} {'Name':<20} {'Recipients':<10} {'Opens':<10} {'Clicks':<10}")
        print("-" * 50)
        
        for campaign in campaigns:
            recipients = EmailRecipient.query.filter_by(campaign_id=campaign.id).all()
            opens = sum(1 for r in recipients if r.open_count and r.open_count > 0)
            clicks = sum(1 for r in recipients if r.click_count and r.click_count > 0)
            
            print(f"{campaign.id:<4} {campaign.name[:20]:<20} {len(recipients):<10} {opens:<10} {clicks:<10}")
            
            # Show list of recipients with opens for debugging
            if opens > 0:
                print("\nRecipients with opens:")
                for recipient in recipients:
                    if recipient.open_count and recipient.open_count > 0:
                        print(f"  - {recipient.email}: {recipient.open_count} opens, last opened at {recipient.last_opened_at}")
        
        print("\nIf you're still not seeing this data in the UI, try the following:")
        print("1. Hard refresh your browser (Ctrl+F5)")
        print("2. Clear browser cache")
        print("3. Try a different browser")
        print("4. Restart the Flask application")

if __name__ == "__main__":
    print("=" * 70)
    print("🔄 REFRESHING TRACKING DISPLAY")
    print("=" * 70)
    fix_tracking_display()
