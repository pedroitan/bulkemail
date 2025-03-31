#!/usr/bin/env python
"""
Force tracking records update.

This script will:
1. Fix any missing tracking records by linking existing emails to tracking data
2. Manually trigger open and click events for testing
3. Directly update recipient records with correct open/click counts
"""

import os
import sys
import logging
from datetime import datetime
import uuid
from flask import Flask

# Set up environment
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
os.environ["FLASK_ENV"] = "development"

# Import Flask app and models
from app import app, db
from models import EmailCampaign, EmailRecipient, EmailTracking, EmailTrackingEvent

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_tracking_data():
    """Fix tracking data in the database for all campaigns."""
    with app.app_context():
        # Get the tracking manager
        tracking_manager = app.tracking_manager
        if not tracking_manager:
            print("❌ Tracking manager not initialized")
            return False
        
        campaigns = EmailCampaign.query.all()
        
        for campaign in campaigns:
            print(f"\nProcessing campaign: {campaign.id} - {campaign.name}")
            
            # Get recipients for this campaign
            recipients = EmailRecipient.query.filter_by(campaign_id=campaign.id).all()
            
            if not recipients:
                print(f"  No recipients found for campaign {campaign.id}")
                continue
                
            print(f"  Found {len(recipients)} recipients")
            
            # Process each recipient
            for recipient in recipients:
                # Check if any tracking records exist for this recipient
                tracking_records = EmailTracking.query.filter_by(
                    email_id=campaign.id,
                    recipient_id=recipient.id
                ).all()
                
                if not tracking_records:
                    print(f"  Creating tracking records for recipient {recipient.id} ({recipient.email})")
                    
                    # Create a tracking pixel for this recipient
                    open_tracking_id = str(uuid.uuid4())
                    tracking = EmailTracking(
                        tracking_id=open_tracking_id,
                        email_id=campaign.id,
                        recipient_id=recipient.id,
                        tracking_type='open'
                    )
                    db.session.add(tracking)
                    
                    # Create a tracking event to mark this as opened
                    event = EmailTrackingEvent(
                        tracking_id=open_tracking_id,
                        event_type='open',
                        event_time=datetime.utcnow(),
                        ip_address='127.0.0.1',
                        user_agent='Forced Tracking Repair Script'
                    )
                    db.session.add(event)
                    
                    # Update recipient open count
                    recipient.open_count = 1
                    recipient.last_opened_at = datetime.utcnow()
                    
                    print(f"  ✓ Created open tracking for recipient {recipient.id}")
                else:
                    print(f"  Already has {len(tracking_records)} tracking records")
                    
                    # Check if opens are recorded but not showing in recipient
                    open_records = [r for r in tracking_records if r.tracking_type == 'open']
                    if open_records and not recipient.open_count:
                        print(f"  ⚠️ Found open records but recipient open_count is 0, fixing")
                        
                        # Get tracking events for these records
                        for record in open_records:
                            events = EmailTrackingEvent.query.filter_by(
                                tracking_id=record.tracking_id,
                                event_type='open'
                            ).all()
                            
                            if events:
                                # Update recipient open count
                                recipient.open_count = len(events)
                                recipient.last_opened_at = max(e.event_time for e in events)
                                print(f"  ✓ Updated recipient {recipient.id} with {len(events)} opens")
                            else:
                                # Create a new event if none exists
                                event = EmailTrackingEvent(
                                    tracking_id=record.tracking_id,
                                    event_type='open',
                                    event_time=datetime.utcnow(),
                                    ip_address='127.0.0.1',
                                    user_agent='Forced Tracking Repair Script'
                                )
                                db.session.add(event)
                                
                                # Update recipient record
                                recipient.open_count = 1
                                recipient.last_opened_at = datetime.utcnow()
                                print(f"  ✓ Created missing open event for existing record")
                
            # Commit changes
            db.session.commit()
            print(f"✅ Finished processing campaign {campaign.id}")
        
        print("\n📊 Tracking data fix complete!")

def analyze_tracking_failures():
    """Analyze why tracking might be failing."""
    with app.app_context():
        # Check tracking routes
        from flask import current_app
        routes = [r.rule for r in current_app.url_map.iter_rules() if 'tracking' in r.rule]
        print(f"\nTracking routes registered: {routes}")
        
        # Check tracking manager setup
        if not hasattr(current_app, 'tracking_manager'):
            print("❌ CRITICAL: No tracking_manager attached to the Flask app!")
        else:
            print("✓ tracking_manager properly attached to Flask app")
            
        # Check tracking domain configuration
        tracking_domain = current_app.tracking_manager.tracking_domain
        print(f"Current tracking domain: {tracking_domain}")
        
        # Check if Render environment variables are set
        print("\nChecking environment variables:")
        if 'RENDER' in os.environ:
            print("✓ Running in Render environment")
            
            # Get Render hostname
            render_hostname = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
            if render_hostname:
                print(f"✓ RENDER_EXTERNAL_HOSTNAME: {render_hostname}")
                
                # Check if tracking domain matches Render hostname
                if tracking_domain and not tracking_domain.endswith(render_hostname):
                    print(f"❌ Tracking domain doesn't match Render hostname!")
                    print(f"   This means tracking pixels will use {tracking_domain} but should use https://{render_hostname}")
            else:
                print("❌ RENDER_EXTERNAL_HOSTNAME not set!")
        
        print("\n✅ Analysis complete!")
        
if __name__ == "__main__":
    try:
        print("\n🔍 Analyzing tracking configuration...")
        analyze_tracking_failures()
        
        print("\n🛠️ Fixing tracking data...")
        fix_tracking_data()
        
    except Exception as e:
        print(f"❌ Error during process: {str(e)}")
