#!/usr/bin/env python
"""
Test script for AWS SNS notifications and delivery status updates
This script will:
1. Send a test email
2. Simulate AWS SNS notifications (delivery and bounce)
3. Check if the database was updated correctly
"""

import os
import sys
import json
import time
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import app and models
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app import get_app
from models import db, EmailCampaign, EmailRecipient

# Test configuration
TEST_EMAIL = "test@example.com"  # Change this to your test email
CAMPAIGN_ID = 1  # Change this to an existing campaign ID
LOCAL_SERVER = "http://localhost:5000"

def create_test_recipient(app, campaign_id, email):
    """Create a test recipient for the specified campaign"""
    with app.app_context():
        # Check if the campaign exists
        campaign = EmailCampaign.query.get(campaign_id)
        if not campaign:
            print(f"Campaign with ID {campaign_id} not found!")
            return None
        
        # Check if the test recipient already exists
        recipient = EmailRecipient.query.filter_by(
            campaign_id=campaign_id,
            email=email,
            is_test=True
        ).first()
        
        # If it exists, reset it
        if recipient:
            recipient.status = 'pending'
            recipient.delivery_status = None
            recipient.message_id = None
            recipient.error_message = None
            db.session.commit()
            print(f"Reset existing test recipient: {email}")
            return recipient
        
        # Create a new test recipient
        recipient = EmailRecipient(
            campaign_id=campaign_id,
            email=email,
            name="Test Recipient",
            status="pending",
            is_test=True
        )
        db.session.add(recipient)
        db.session.commit()
        print(f"Created new test recipient: {email}")
        return recipient

def send_test_email(app, campaign_id, email):
    """Send a test email and return the message ID"""
    print(f"Sending test email to {email}...")
    
    # Send the test email via the API
    response = requests.post(
        f"{LOCAL_SERVER}/api/campaigns/{campaign_id}/send-test",
        json={"email": email}
    )
    
    if response.status_code != 200:
        print(f"Error sending test email: {response.text}")
        return None
    
    data = response.json()
    if not data.get('success'):
        print(f"Failed to send test email: {data.get('message')}")
        return None
    
    print(f"Test email sent successfully!")
    
    # Get the message ID from the database
    with app.app_context():
        recipient = EmailRecipient.query.filter_by(
            campaign_id=campaign_id,
            email=email,
            is_test=True
        ).first()
        
        if not recipient:
            print("Could not find recipient in database!")
            return None
        
        print(f"Message ID: {recipient.message_id}")
        print(f"Initial status: {recipient.status}")
        print(f"Initial delivery status: {recipient.delivery_status}")
        
        return recipient.message_id

def simulate_delivery_notification(app, message_id, email):
    """Simulate an AWS SNS delivery notification"""
    print(f"\nSimulating delivery notification for {email}...")
    
    # Create a delivery notification payload
    delivery_time = datetime.now().isoformat() + "Z"
    
    notification = {
        "Type": "Notification",
        "Message": json.dumps({
            "notificationType": "Delivery",
            "mail": {
                "timestamp": (datetime.now() - timedelta(minutes=1)).isoformat() + "Z",
                "messageId": message_id,
                "source": os.environ.get("SENDER_EMAIL"),
                "destination": [email]
            },
            "delivery": {
                "timestamp": delivery_time,
                "recipients": [email],
                "processingTimeMillis": 500,
                "reportingMTA": "a8-50.smtp-out.amazonses.com",
                "smtpResponse": "250 2.6.0 Message received",
                "remoteMtaIp": "127.0.0.1"
            }
        })
    }
    
    # Send the notification to the SNS endpoint
    response = requests.post(
        f"{LOCAL_SERVER}/api/sns/ses-notification",
        json=notification,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code != 200:
        print(f"Error sending delivery notification: {response.text}")
        return False
    
    print("Delivery notification sent successfully!")
    return True

def simulate_bounce_notification(app, message_id, email):
    """Simulate an AWS SNS bounce notification"""
    print(f"\nSimulating bounce notification for {email}...")
    
    # Create a bounce notification payload
    bounce_time = datetime.now().isoformat() + "Z"
    
    notification = {
        "Type": "Notification",
        "Message": json.dumps({
            "notificationType": "Bounce",
            "mail": {
                "timestamp": (datetime.now() - timedelta(minutes=1)).isoformat() + "Z",
                "messageId": message_id,
                "source": os.environ.get("SENDER_EMAIL"),
                "destination": [email]
            },
            "bounce": {
                "bounceType": "Permanent",
                "bounceSubType": "General",
                "bouncedRecipients": [
                    {
                        "emailAddress": email,
                        "action": "failed",
                        "status": "5.1.1",
                        "diagnosticCode": "Test bounce notification"
                    }
                ],
                "timestamp": bounce_time,
                "feedbackId": "0100017123456789-12345678-9012-3456-7890-123456789012-000000"
            }
        })
    }
    
    # Send the notification to the SNS endpoint
    response = requests.post(
        f"{LOCAL_SERVER}/api/sns/ses-notification",
        json=notification,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code != 200:
        print(f"Error sending bounce notification: {response.text}")
        return False
    
    print("Bounce notification sent successfully!")
    return True

def check_recipient_status(app, campaign_id, email):
    """Check the status of a recipient in the database"""
    print(f"\nChecking status for {email}...")
    
    with app.app_context():
        recipient = EmailRecipient.query.filter_by(
            campaign_id=campaign_id,
            email=email,
            is_test=True
        ).first()
        
        if not recipient:
            print("Could not find recipient in database!")
            return False
        
        print(f"Current status: {recipient.status}")
        print(f"Delivery status: {recipient.delivery_status}")
        print(f"Message ID: {recipient.message_id}")
        
        if recipient.bounce_type:
            print(f"Bounce type: {recipient.bounce_type}")
            print(f"Bounce subtype: {recipient.bounce_subtype}")
            print(f"Bounce diagnostic: {recipient.bounce_diagnostic}")
        
        return recipient

def run_delivery_test(app, campaign_id, email):
    """Run a complete delivery test"""
    print("=== RUNNING DELIVERY TEST ===")
    
    # Create or reset the test recipient
    recipient = create_test_recipient(app, campaign_id, email)
    if not recipient:
        return False
    
    # Send a test email
    message_id = send_test_email(app, campaign_id, email)
    if not message_id:
        return False
    
    # Wait a moment for the email to be sent
    print("Waiting 2 seconds...")
    time.sleep(2)
    
    # Simulate a delivery notification
    if not simulate_delivery_notification(app, message_id, email):
        return False
    
    # Wait a moment for the notification to be processed
    print("Waiting 2 seconds...")
    time.sleep(2)
    
    # Check the recipient status
    recipient = check_recipient_status(app, campaign_id, email)
    
    # Verify the delivery status was updated
    if recipient and recipient.delivery_status == 'delivered':
        print("\n✅ SUCCESS: Delivery status was correctly updated to 'delivered'")
        return True
    else:
        print("\n❌ FAILURE: Delivery status was not updated correctly")
        return False

def run_bounce_test(app, campaign_id, email):
    """Run a complete bounce test"""
    print("\n=== RUNNING BOUNCE TEST ===")
    
    # Create or reset the test recipient
    recipient = create_test_recipient(app, campaign_id, email)
    if not recipient:
        return False
    
    # Send a test email
    message_id = send_test_email(app, campaign_id, email)
    if not message_id:
        return False
    
    # Wait a moment for the email to be sent
    print("Waiting 2 seconds...")
    time.sleep(2)
    
    # Simulate a bounce notification
    if not simulate_bounce_notification(app, message_id, email):
        return False
    
    # Wait a moment for the notification to be processed
    print("Waiting 2 seconds...")
    time.sleep(2)
    
    # Check the recipient status
    recipient = check_recipient_status(app, campaign_id, email)
    
    # Verify the bounce status was updated
    if recipient and recipient.delivery_status == 'bounced' and recipient.status == 'failed':
        print("\n✅ SUCCESS: Bounce status was correctly updated")
        return True
    else:
        print("\n❌ FAILURE: Bounce status was not updated correctly")
        return False

if __name__ == "__main__":
    # Get the Flask app
    app = get_app()
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Test AWS SNS notifications')
    parser.add_argument('--email', type=str, default=TEST_EMAIL,
                        help='Email address to use for testing')
    parser.add_argument('--campaign', type=int, default=CAMPAIGN_ID,
                        help='Campaign ID to use for testing')
    parser.add_argument('--test', type=str, choices=['delivery', 'bounce', 'both'], default='both',
                        help='Which test to run')
    
    args = parser.parse_args()
    
    # Run the tests
    if args.test in ['delivery', 'both']:
        delivery_success = run_delivery_test(app, args.campaign, args.email)
    else:
        delivery_success = True
    
    if args.test in ['bounce', 'both']:
        bounce_success = run_bounce_test(app, args.campaign, args.email)
    else:
        bounce_success = True
    
    # Print final results
    print("\n=== TEST RESULTS ===")
    if args.test in ['delivery', 'both']:
        print(f"Delivery Test: {'✅ PASSED' if delivery_success else '❌ FAILED'}")
    if args.test in ['bounce', 'both']:
        print(f"Bounce Test: {'✅ PASSED' if bounce_success else '❌ FAILED'}")
    
    if delivery_success and bounce_success:
        print("\n🎉 All tests passed! Your notification handling is working correctly.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Check the logs for details.")
        sys.exit(1)
