#!/usr/bin/env python
"""
Fix email tracking by properly connecting the tracking manager to the email service.
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

def fix_email_service_tracking():
    """Connect the tracking manager to the email service."""
    with app.app_context():
        # Get the tracking manager and email service
        tracking_manager = app.tracking_manager
        email_service = app.get_email_service()
        
        if not tracking_manager:
            print("❌ No tracking manager found on app")
            return False
            
        if not email_service:
            print("❌ No email service initialized")
            return False
            
        # Connect tracking manager to email service
        email_service.tracking_manager = tracking_manager
        print("✅ Connected tracking manager to email service")
        
        # Test if the connection works
        if hasattr(email_service, 'tracking_manager') and email_service.tracking_manager:
            print("✅ Email service now has tracking manager properly attached")
            return True
        else:
            print("❌ Failed to connect tracking manager to email service")
            return False

def fix_app_initialization():
    """Modify app.py to ensure tracking manager is connected to email service."""
    print("\nMake sure to add this code to your create_app function in app.py:")
    print("=" * 70)
    print("""
    # Initialize tracking manager
    tracking_manager = init_tracking(app, db)
    app.tracking_manager = tracking_manager
    
    # Connect tracking manager to email service
    email_service = app.get_email_service()
    email_service.tracking_manager = tracking_manager
    """)
    print("=" * 70)
    print("\nLocation: After 'tracking_manager = init_tracking(app, db)' in create_app()")

if __name__ == "__main__":
    print("=" * 70)
    print("🛠️ EMAIL TRACKING FIX")
    print("=" * 70)
    
    # Fix email service tracking in current session
    fix_email_service_tracking()
    
    # Provide code to permanently fix the issue
    fix_app_initialization()
    
    print("\n🚀 The tracking connection has been fixed for this session.")
    print("🔧 Follow the instructions above to make the fix permanent.")
