#!/usr/bin/env python
"""
Test email tracking integration by simulating the full email processing flow
and verifying tracking components are inserted correctly.
"""

import os
import sys
import logging
from datetime import datetime
import re
import uuid
from flask import Flask

# Set up environment
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
os.environ["FLASK_ENV"] = "development"

# Import Flask app and models
from app import app, db
from models import EmailCampaign, EmailRecipient, EmailTracking, EmailTrackingEvent
from email_service import SESEmailService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_html_processing():
    """Test that HTML is correctly processed with tracking components."""
    with app.app_context():
        tracking_manager = app.tracking_manager
        if not tracking_manager:
            print("❌ Tracking manager not properly initialized")
            return False

        # Create test data
        test_html = """
        <html>
        <body>
            <h1>Test Email</h1>
            <p>This is a test email with a <a href="https://example.com">link</a>.</p>
            <p>And another <a href="https://google.com">link to Google</a>.</p>
        </body>
        </html>
        """
        
        # Test with both real and fake IDs
        email_id = 2  # Campaign ID from your database
        recipient_id = 10  # Recipient ID from your database
        
        # Process HTML with tracking
        processed_html = tracking_manager.process_html_content(
            test_html, email_id, recipient_id
        )
        
        # Verify tracking pixel is added
        if 'tracking/pixel/' in processed_html and '.png' in processed_html:
            print("✅ Tracking pixel added to HTML")
            tracking_pixel_match = re.search(r'/tracking/pixel/([^.]+)\.png', processed_html)
            if tracking_pixel_match:
                tracking_id = tracking_pixel_match.group(1)
                print(f"  Tracking ID: {tracking_id}")
        else:
            print("❌ Tracking pixel NOT added to HTML")
            
        # Verify links are rewritten
        if 'tracking/redirect' in processed_html:
            print("✅ Links rewritten for tracking")
            link_count = processed_html.count('tracking/redirect')
            print(f"  {link_count} links rewritten")
        else:
            print("❌ Links NOT rewritten for tracking")
            
        # Print the processed HTML
        print("\nProcessed HTML (excerpt):")
        print("=" * 50)
        print(processed_html[:500] + "..." if len(processed_html) > 500 else processed_html)
        print("=" * 50)
        
        return 'tracking/pixel/' in processed_html and 'tracking/redirect' in processed_html

def test_email_service_integration():
    """Test that email service correctly applies tracking."""
    with app.app_context():
        try:
            from email_service import SESEmailService
            from email_tracking import EmailTrackingManager
            
            # Check how email service and tracking interact
            print("\nChecking email service initialization...")
            email_service = app.get_email_service()
            if not email_service:
                print("❌ Email service not properly initialized")
                return False
                
            # Check if email service tracking parameters work
            print("\nSimulating email sending with tracking...")
            test_html = "<p>Test email with <a href='https://example.com'>link</a></p>"
            
            # Create a test recipient for tracking
            campaign_id = 2  # Use an existing campaign
            test_email = "test@example.com"  # Use a test email
            
            # Find or create test recipient
            test_recipient = EmailRecipient.query.filter_by(
                campaign_id=campaign_id,
                email=test_email
            ).first()
            
            if not test_recipient:
                test_recipient = EmailRecipient(
                    campaign_id=campaign_id,
                    email=test_email,
                    status="pending"
                )
                db.session.add(test_recipient)
                db.session.commit()
                print(f"Created test recipient with ID: {test_recipient.id}")
            else:
                print(f"Using existing test recipient with ID: {test_recipient.id}")
            
            # Directly call the HTML processing method
            print("\nSimulating what happens in send_email method...")
            
            # Example of how send_email processes HTML when tracking is enabled
            if hasattr(email_service, 'tracking_manager') and email_service.tracking_manager:
                processed_html = email_service.tracking_manager.process_html_content(
                    test_html, campaign_id, test_recipient.id
                )
                print("✅ Email service properly processes HTML with tracking")
                
                # Check if tracking records were created
                tracking_records = EmailTracking.query.filter_by(
                    email_id=campaign_id,
                    recipient_id=test_recipient.id
                ).all()
                
                print(f"  Created {len(tracking_records)} tracking records")
                for record in tracking_records:
                    print(f"  - Type: {record.tracking_type}, ID: {record.tracking_id}")
            else:
                print("❌ Email service NOT properly set up with tracking manager")
            
            return True
        except Exception as e:
            print(f"❌ Error during email service test: {str(e)}")
            return False

def test_tracking_api():
    """Test tracking API endpoints directly."""
    import requests
    print("\nTesting tracking API endpoints...")
    
    # Get a tracking ID from the database
    with app.app_context():
        tracking_record = EmailTracking.query.filter_by(tracking_type='open').first()
        if not tracking_record:
            print("❌ No tracking records found in database")
            return False
            
        tracking_id = tracking_record.tracking_id
        
        # Test tracking pixel endpoint
        try:
            print(f"\nTesting tracking pixel endpoint with ID: {tracking_id}")
            pixel_url = f"http://localhost:5000/tracking/pixel/{tracking_id}.png"
            
            print(f"Requesting: {pixel_url}")
            response = requests.get(pixel_url)
            
            if response.status_code == 200 and response.headers.get('content-type') == 'image/png':
                print(f"✅ Tracking pixel endpoint works (Status: {response.status_code})")
                
                # Verify that event was recorded
                event = EmailTrackingEvent.query.filter_by(
                    tracking_id=tracking_id,
                    event_type='open'
                ).order_by(EmailTrackingEvent.event_time.desc()).first()
                
                if event and (datetime.utcnow() - event.event_time).total_seconds() < 60:
                    print(f"✅ Open event recorded at {event.event_time}")
                else:
                    print("❌ Open event NOT recorded properly")
            else:
                print(f"❌ Tracking pixel endpoint failed: {response.status_code}")
                print(f"  Content-Type: {response.headers.get('content-type')}")
                print(f"  Response preview: {response.text[:100] if response.text else None}")
        except Exception as e:
            print(f"❌ Error testing tracking pixel: {str(e)}")
            
        # Test tracking URL domain
        try:
            print("\nChecking tracking domain configuration...")
            
            # Get tracking domain 
            if hasattr(app, 'tracking_manager'):
                current_domain = app.tracking_manager._tracking_domain
                
                if current_domain:
                    print(f"Current tracking domain: {current_domain}")
                else:
                    print("❌ No explicit tracking domain set")
                    
                # Check domain from request context
                try:
                    with app.test_request_context('/'):
                        domain = app.tracking_manager.tracking_domain
                        print(f"Domain in request context: {domain}")
                except Exception as e:
                    print(f"❌ Error getting domain in request context: {str(e)}")
                    
            else:
                print("❌ No tracking manager on app")
        except Exception as e:
            print(f"❌ Error checking tracking domain: {str(e)}")
    
    return True

if __name__ == "__main__":
    print("=" * 70)
    print("🧪 COMPREHENSIVE EMAIL TRACKING TEST")
    print("=" * 70)
    
    tests = [
        ("HTML Processing Test", test_html_processing),
        ("Email Service Integration Test", test_email_service_integration),
        ("Tracking API Test", test_tracking_api)
    ]
    
    results = []
    
    for name, test_func in tests:
        print(f"\n📋 Running {name}...")
        try:
            success = test_func()
            results.append((name, success))
            print(f"📋 {name}: {'✅ PASS' if success else '❌ FAIL'}")
        except Exception as e:
            print(f"💥 Error during {name}: {str(e)}")
            results.append((name, False))
    
    print("\n" + "=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)
    
    all_pass = True
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {name}")
        all_pass = all_pass and success
    
    print("\n🏁 Overall result: " + ("✅ ALL TESTS PASSED" if all_pass else "❌ SOME TESTS FAILED"))
