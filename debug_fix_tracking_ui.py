#!/usr/bin/env python
"""
Fix script that verifies whether tracking data is properly displayed in the UI
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

def test_tracking_route_data():
    """Test the exact data that would be displayed by the tracking routes"""
    with app.app_context():
        # Get a campaign with opens we know exists (from previous debug output)
        campaign_id = 2  # "Bounce Test Campaign" which had 9 opens
        
        print(f"Testing tracking report for campaign ID {campaign_id}")
        
        # Get the campaign
        campaign = EmailCampaign.query.get(campaign_id)
        if not campaign:
            print(f"Campaign with ID {campaign_id} not found!")
            return
            
        print(f"Campaign: {campaign.name} (ID: {campaign.id})")
        
        # Get all recipients for this campaign
        recipients = EmailRecipient.query.filter_by(campaign_id=campaign_id).all()
        
        # Check raw open counts
        opens_count = 0
        for recipient in recipients:
            if recipient.open_count and recipient.open_count > 0:
                opens_count += 1
                print(f"Recipient {recipient.email} has {recipient.open_count} opens")
                
        print(f"Total {opens_count} recipients with opens")
        
        # Replicate the exact logic from tracking_report_campaign
        total_recipients = len(recipients)
        total_opens = sum(1 for r in recipients if r.open_count and r.open_count > 0)
        
        print(f"Logic in route would calculate: {total_opens} total opens out of {total_recipients} recipients")
        
        # Get recipients who opened emails - exact logic from the route
        open_stats = [r for r in recipients if r.open_count and r.open_count > 0]
        open_stats.sort(key=lambda x: x.open_count or 0, reverse=True)
        
        print(f"open_stats would contain {len(open_stats)} items")
        
        for i, recipient in enumerate(open_stats):
            print(f"{i+1}. {recipient.email}: {recipient.open_count} opens")
            
        # Check if any attribute of EmailRecipient might be protected or not accessible correctly
        if open_stats:
            first = open_stats[0]
            print("\nFirst recipient in open_stats:")
            print(f"Email: {first.email}")
            print(f"Type of open_count: {type(first.open_count)}")
            print(f"Value of open_count: {first.open_count}")
            print(f"Last opened at: {first.last_opened_at}")

def validate_tracking_campaigns_template():
    """Check if the tracking_campaigns.html template properly shows open counts"""
    with app.app_context():
        # Get all campaigns with tracking data
        campaigns = EmailCampaign.query.all()
        
        print("\nCampaigns with tracking data:")
        for campaign in campaigns:
            total_recipients = EmailRecipient.query.filter_by(campaign_id=campaign.id).count()
            recipients_with_opens = EmailRecipient.query.filter_by(
                campaign_id=campaign.id
            ).filter(EmailRecipient.open_count > 0).count()
            
            print(f"Campaign {campaign.id} ({campaign.name}): {recipients_with_opens}/{total_recipients} opens")

if __name__ == "__main__":
    print("=" * 70)
    print("🔧 DEBUGGING TRACKING UI ISSUE")
    print("=" * 70)
    test_tracking_route_data()
    validate_tracking_campaigns_template()
    print("\nRunning this test helps determine if the issue is in the route logic or the template rendering.")
