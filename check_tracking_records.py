#!/usr/bin/env python
"""
Diagnostic script to check tracking records in the database.
This will help identify why email opens are not showing in the UI.
"""

import os
import sys
import logging
from datetime import datetime, timedelta

# Set up proper environment
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
os.environ["FLASK_ENV"] = "development"

# Import Flask app and models
from app import app, db
from models import EmailCampaign, EmailRecipient, EmailTracking, EmailTrackingEvent

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_campaign_tracking(campaign_id=None):
    """Check tracking records for a specific campaign or all campaigns."""
    with app.app_context():
        if campaign_id:
            campaigns = [EmailCampaign.query.get(campaign_id)]
            if not campaigns[0]:
                print(f"❌ No campaign found with ID {campaign_id}")
                return
        else:
            campaigns = EmailCampaign.query.all()
            if not campaigns:
                print("❌ No campaigns found in the database")
                return
        
        print(f"Found {len(campaigns)} campaigns")
        
        for campaign in campaigns:
            print("\n" + "=" * 50)
            print(f"Campaign ID: {campaign.id} - {campaign.name}")
            print(f"Status: {campaign.status}")
            
            # Get recipients for this campaign
            recipients = EmailRecipient.query.filter_by(campaign_id=campaign.id).all()
            print(f"Recipients: {len(recipients)}")
            
            # Get tracking records for this campaign
            tracking_records = EmailTracking.query.filter_by(email_id=campaign.id).all()
            print(f"Tracking records: {len(tracking_records)}")
            
            # Count open and click records
            open_records = [r for r in tracking_records if r.tracking_type == 'open']
            click_records = [r for r in tracking_records if r.tracking_type == 'click']
            print(f"Open tracking records: {len(open_records)}")
            print(f"Click tracking records: {len(click_records)}")
            
            # Check tracking events
            tracking_events = EmailTrackingEvent.query.join(
                EmailTracking, EmailTrackingEvent.tracking_id == EmailTracking.tracking_id
            ).filter(
                EmailTracking.email_id == campaign.id
            ).all()
            print(f"Tracking events: {len(tracking_events)}")
            
            # Count open and click events
            open_events = [e for e in tracking_events if e.event_type == 'open']
            click_events = [e for e in tracking_events if e.event_type == 'click']
            print(f"Open events: {len(open_events)}")
            print(f"Click events: {len(click_events)}")
            
            # Check recipients with open counts
            recipients_with_opens = [r for r in recipients if r.open_count and r.open_count > 0]
            print(f"Recipients with open counts: {len(recipients_with_opens)}")
            for recipient in recipients_with_opens:
                print(f"  - {recipient.email}: {recipient.open_count} opens, last at {recipient.last_opened_at}")
            
            if len(recipients_with_opens) == 0:
                print("  ❌ No recipients have open counts!")
                
                # Check if tracking pixel URLs were generated but not triggered
                if len(open_records) > 0:
                    print("  ⚠️ Tracking pixels were generated but never triggered!")
                    print("  This usually means the recipient's email client blocked images.")
            
            # Check for discrepancies
            if len(open_events) > 0 and len(recipients_with_opens) == 0:
                print("  ❗ DISCREPANCY: Open events exist but recipient open counts are zero")
                print("  This indicates the UI is reading from recipient.open_count but events aren't updating it")
            
            print("=" * 50)

if __name__ == "__main__":
    try:
        if len(sys.argv) > 1:
            campaign_id = int(sys.argv[1])
            check_campaign_tracking(campaign_id)
        else:
            check_campaign_tracking()
            
        print("\nTracking Check Complete!")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
