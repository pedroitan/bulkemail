#!/usr/bin/env python
"""
Reset tracking data for invalid email addresses.
This script resets open_count to 0 for recipients with clearly invalid email addresses.
"""

import os
import sys
import re
from datetime import datetime
from flask import Flask

# Set up environment
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
os.environ["FLASK_ENV"] = "development"

# Import Flask app and models
from app import app, db
from models import EmailRecipient, EmailTracking, EmailTrackingEvent

def is_invalid_email(email):
    """Check if email is obviously invalid based on simple patterns."""
    # Check for non-existent TLDs
    invalid_tlds = ['.come', '.con', '.cmo', '.comn', '.cpm']
    for tld in invalid_tlds:
        if email.endswith(tld):
            return True
    
    # Check for clearly malformed emails
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        return True
        
    # List of known invalid addresses
    known_invalid = ['asldkj@dlskj.come', 'asdf@asdasdfasd.com', 'psodli@gmalihs.com']
    if email in known_invalid:
        return True
    
    return False

def reset_invalid_opens():
    """Reset open tracking for invalid email addresses."""
    with app.app_context():
        # Get all recipients
        recipients = EmailRecipient.query.all()
        
        print(f"Found {len(recipients)} total recipients")
        reset_count = 0
        
        for recipient in recipients:
            if is_invalid_email(recipient.email):
                print(f"Resetting invalid email: {recipient.email}")
                
                # Reset open count
                recipient.open_count = 0
                recipient.last_opened_at = None
                
                # Find and delete related tracking events
                tracking_records = EmailTracking.query.filter_by(
                    recipient_id=recipient.id,
                    tracking_type='open'
                ).all()
                
                for record in tracking_records:
                    events = EmailTrackingEvent.query.filter_by(
                        tracking_id=record.tracking_id,
                        event_type='open'
                    ).all()
                    
                    for event in events:
                        db.session.delete(event)
                
                reset_count += 1
        
        # Commit changes
        db.session.commit()
        print(f"Reset {reset_count} invalid email recipients")

if __name__ == "__main__":
    try:
        reset_invalid_opens()
        print("✅ Completed resetting invalid email tracking")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
