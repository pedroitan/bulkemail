#!/usr/bin/env python
"""
Test script for email tracking functionality
This script verifies that email tracking is working correctly by:
1. Testing that tracking pixels are added to emails
2. Testing that links are properly rewritten for click tracking
3. Verifying database entries are created
"""

import os
import sys
from datetime import datetime, timedelta
from flask import Flask

# Set up proper environment for Flask app
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
os.environ["FLASK_ENV"] = "development"

# Import the Flask application
from app import app, db
from models import EmailCampaign, EmailRecipient, EmailTracking, EmailTrackingEvent
from email_tracking import EmailTrackingManager

def test_tracking():
    """Test the email tracking functionality"""
    print("Starting email tracking test...")
    
    with app.app_context():
        # Create a test tracking manager
        tracking_manager = app.tracking_manager
        if not tracking_manager:
            print("ERROR: Tracking manager not initialized")
            return False
        
        # Create test campaign and recipient for tracking
        test_campaign = EmailCampaign(
            name="Tracking Test Campaign",
            subject="Tracking Test",
            body_html="""
            <html>
            <body>
                <h1>Test Email</h1>
                <p>This is a test email with a <a href="https://example.com">link</a>.</p>
                <p>And another <a href="https://test.com">link</a>.</p>
            </body>
            </html>
            """,
            scheduled_time=datetime.now() + timedelta(days=1),  # Schedule for tomorrow
            status="draft",
            sender_email="test@example.com",
            sender_name="Test Sender"
        )
        db.session.add(test_campaign)
        db.session.commit()
        
        test_recipient = EmailRecipient(
            campaign_id=test_campaign.id,
            email="test@example.com",
            status="pending"
        )
        db.session.add(test_recipient)
        db.session.commit()
        
        print(f"Created test campaign ID: {test_campaign.id}")
        print(f"Created test recipient ID: {test_recipient.id}")
        
        # Test tracking pixel generation
        tracking_pixel_url = tracking_manager.generate_tracking_pixel(
            test_campaign.id, test_recipient.id
        )
        print(f"Generated tracking pixel URL: {tracking_pixel_url}")
        
        # Test link tracking
        tracking_link = tracking_manager.generate_tracking_link(
            test_campaign.id, test_recipient.id, "https://example.com"
        )
        print(f"Generated tracking link: {tracking_link}")
        
        # Test HTML processing
        processed_html = tracking_manager.process_html_content(
            test_campaign.body_html, test_campaign.id, test_recipient.id
        )
        print("\nProcessed HTML with tracking:")
        print("=" * 50)
        print(processed_html[:500] + "..." if len(processed_html) > 500 else processed_html)
        print("=" * 50)
        
        # Check if tracking pixel is in the HTML
        if 'tracking/pixel/' in processed_html:
            print("✓ Tracking pixel found in HTML")
        else:
            print("✗ Tracking pixel NOT found in HTML")
            
        # Check if links are rewritten
        if 'tracking/redirect' in processed_html:
            print("✓ Tracking links found in HTML")
        else:
            print("✗ Tracking links NOT found in HTML")
        
        # Verify tracking records in database
        tracking_records = EmailTracking.query.filter_by(
            email_id=test_campaign.id,
            recipient_id=test_recipient.id
        ).all()
        
        print(f"\nFound {len(tracking_records)} tracking records in database")
        for record in tracking_records:
            print(f"  - Type: {record.tracking_type}, ID: {record.tracking_id}")
        
        # Clean up test data
        print("\nCleaning up test data...")
        for record in tracking_records:
            db.session.delete(record)
        db.session.delete(test_recipient)
        db.session.delete(test_campaign)
        db.session.commit()
        
        success = len(tracking_records) >= 3  # 1 pixel + 2 links
        return success

if __name__ == "__main__":
    try:
        with app.app_context():
            success = test_tracking()
            if success:
                print("\n✅ Email tracking test completed successfully!")
            else:
                print("\n❌ Email tracking test failed!")
    except Exception as e:
        print(f"\n❌ Error during testing: {str(e)}")
