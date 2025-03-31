#!/usr/bin/env python
"""
Check if tracking pixels are being accessed and properly updating the database.
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

def check_tracking_events():
    """Check if any tracking events have been recorded in the last 24 hours."""
    with app.app_context():
        # Check for recent tracking events
        yesterday = datetime.now() - timedelta(days=1)
        
        events = EmailTrackingEvent.query.filter(
            EmailTrackingEvent.event_time > yesterday
        ).order_by(EmailTrackingEvent.event_time.desc()).all()
        
        print(f"Found {len(events)} tracking events in the last 24 hours:")
        
        for event in events:
            print(f"  - ID: {event.id}")
            print(f"    Tracking ID: {event.tracking_id}")
            print(f"    Type: {event.event_type}")
            print(f"    Time: {event.event_time}")
            print(f"    IP: {event.ip_address}")
            
            # Get related tracking record
            tracking = EmailTracking.query.filter_by(tracking_id=event.tracking_id).first()
            if tracking:
                print(f"    Related to: Campaign {tracking.email_id}, Recipient {tracking.recipient_id}")
                
                # Get recipient info
                recipient = EmailRecipient.query.get(tracking.recipient_id)
                if recipient:
                    print(f"    Recipient email: {recipient.email}")
                    print(f"    Open count: {recipient.open_count}")
                    print(f"    Last opened: {recipient.last_opened_at}")
            
            print()
        
        if not events:
            print("No tracking events found in the last 24 hours.")
            print("\nThis indicates one of several issues:")
            print("1. The tracking pixel requests are not reaching your server")
            print("2. The tracking endpoints aren't properly recording events")
            print("3. Email clients are blocking the tracking pixel")

def verify_tracking_db_records():
    """Check if tracking records exist in the database."""
    with app.app_context():
        # Get counts from each tracking-related table
        tracking_count = EmailTracking.query.count()
        event_count = EmailTrackingEvent.query.count()
        
        recipients_with_opens = EmailRecipient.query.filter(EmailRecipient.open_count > 0).count()
        
        print("\nTracking Database Stats:")
        print(f"Total tracking records: {tracking_count}")
        print(f"Total tracking events: {event_count}")
        print(f"Recipients with opens: {recipients_with_opens}")
        
        if tracking_count > 0 and event_count == 0:
            print("\n⚠️ Warning: You have tracking records but no events!")
            print("This suggests that tracking pixels are being generated but never accessed.")
        
        if event_count > 0 and recipients_with_opens == 0:
            print("\n⚠️ Warning: You have tracking events but no recipients show opens!")
            print("This suggests a disconnection between events and recipient records.")

if __name__ == "__main__":
    print("=" * 70)
    print("🔍 CHECKING EMAIL TRACKING EVENTS")
    print("=" * 70)
    
    check_tracking_events()
    verify_tracking_db_records()
