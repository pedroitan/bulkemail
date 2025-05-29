#!/usr/bin/env python
"""
Debug the tracking UI to understand why opens are not showing in the interface.
"""

import os
import sys
import logging
from datetime import datetime, timedelta

# Set up environment
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
os.environ["FLASK_ENV"] = "development"

# Import Flask app and models
from app import app, db
from models import EmailCampaign, EmailRecipient, EmailTracking, EmailTrackingEvent

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_tracking_report():
    """Debug how the tracking report data is calculated."""
    with app.app_context():
        print("=" * 70)
        print("🔍 EXAMINING TRACKING REPORT DATA")
        print("=" * 70)
        
        # Get all campaigns
        campaigns = EmailCampaign.query.all()
        print(f"Found {len(campaigns)} campaigns")
        
        for campaign in campaigns:
            print(f"\nCampaign ID: {campaign.id} - {campaign.name}")
            print(f"Status: {campaign.status}")
            
            # Get recipients
            recipients = EmailRecipient.query.filter_by(campaign_id=campaign.id).all()
            print(f"Total recipients: {len(recipients)}")
            
            # Count opens directly from recipients
            opens_from_recipients = sum(1 for r in recipients if r.open_count and r.open_count > 0)
            print(f"Recipients with opens (from recipient.open_count): {opens_from_recipients}")
            
            # Count opens from tracking events
            tracking_records = EmailTracking.query.filter_by(
                email_id=campaign.id,
                tracking_type='open'
            ).all()
            
            tracking_ids = [r.tracking_id for r in tracking_records]
            events = EmailTrackingEvent.query.filter(
                EmailTrackingEvent.tracking_id.in_(tracking_ids),
                EmailTrackingEvent.event_type == 'open'
            ).all()
            
            print(f"Tracking records: {len(tracking_records)}")
            print(f"Tracking events: {len(events)}")
            
            # Examine recipients with opens
            if opens_from_recipients > 0:
                print("\nRecipients with opens:")
                for recipient in recipients:
                    if recipient.open_count and recipient.open_count > 0:
                        print(f"  - {recipient.email}: {recipient.open_count} opens, last at {recipient.last_opened_at}")
            
            # Check what the UI would do to calculate opens
            # This simulates the logic from tracking_report_campaign route
            total_recipients = len(recipients)
            total_opens = sum(1 for r in recipients if r.open_count and r.open_count > 0)
            print(f"\nUI would show: {total_opens} opens out of {total_recipients} recipients")
            
            # Verify if any template logic might be interfering
            if total_opens > 0 and opens_from_recipients == 0:
                print("⚠️ Discrepancy: Total opens is positive but no recipients have opens!")
            
            print("-" * 50)

def test_tracking_report_route():
    """Test the actual tracking report route in a test client."""
    with app.app_context():
        print("\n" + "=" * 70)
        print("🧪 TESTING TRACKING REPORT ROUTE")
        print("=" * 70)
        
        # Create a test client
        with app.test_client() as client:
            # Test the tracking page
            response = client.get("/tracking")
            
            if response.status_code == 200:
                print(f"✅ /tracking route returns 200 OK")
                
                # Check a specific campaign report
                campaign = EmailCampaign.query.first()
                if campaign:
                    campaign_response = client.get(f"/tracking/report/{campaign.id}")
                    
                    if campaign_response.status_code == 200:
                        print(f"✅ /tracking/report/{campaign.id} route returns 200 OK")
                        
                        # Check the response data
                        campaign_html = campaign_response.data.decode('utf-8')
                        
                        # Look for open stats in the HTML
                        if "open-count" in campaign_html:
                            print("Found 'open-count' in response HTML")
                        else:
                            print("⚠️ 'open-count' not found in response HTML")
                        
                        # Save HTML for inspection
                        with open('tracking_report_debug.html', 'w') as f:
                            f.write(campaign_html)
                            print(f"Saved response HTML to tracking_report_debug.html for inspection")
                    else:
                        print(f"❌ /tracking/report/{campaign.id} route returns {campaign_response.status_code}")
            else:
                print(f"❌ /tracking route returns {response.status_code}")

if __name__ == "__main__":
    debug_tracking_report()
    test_tracking_report_route()
