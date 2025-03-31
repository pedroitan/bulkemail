"""
Direct Bounce and Delivery Tester

This script simulates SNS notifications by directly calling the Flask endpoint
to test if the bounce and delivery status updates are working correctly.
It respects the lazy initialization pattern used in the application.
"""

import os
import sys
import json
import time
from datetime import datetime
import logging
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import app following the lazy initialization pattern
from app import get_app
from models import EmailCampaign, EmailRecipient, db

# Define SES notification templates based on AWS format
def create_notification_message(notification_type, recipient_email, message_id):
    """Create an SNS notification message for the specified type"""
    base_message = {
        "Type": "Notification",
        "MessageId": "notification-" + datetime.now().isoformat(),
        "TopicArn": "arn:aws:sns:us-east-1:123456789012:ses-notifications",
        "Timestamp": datetime.now().isoformat(),
        "SignatureVersion": "1",
        "Signature": "test-signature",
        "SigningCertURL": "https://sns.us-east-1.amazonaws.com/SimpleNotificationService.pem",
        "UnsubscribeURL": "https://aws.example.com/unsubscribe"
    }
    
    if notification_type == "Bounce":
        base_message["Message"] = json.dumps({
            "notificationType": "Bounce",
            "bounce": {
                "bounceType": "Permanent",
                "bounceSubType": "General",
                "bouncedRecipients": [
                    {
                        "emailAddress": recipient_email,
                        "action": "failed",
                        "status": "5.1.1",
                        "diagnosticCode": "Test bounce diagnostic"
                    }
                ],
                "timestamp": datetime.now().isoformat(),
                "feedbackId": "test-feedback-id"
            },
            "mail": {
                "messageId": message_id,
                "destination": [recipient_email]
            }
        })
        
    elif notification_type == "Delivery":
        base_message["Message"] = json.dumps({
            "notificationType": "Delivery",
            "delivery": {
                "timestamp": datetime.now().isoformat(),
                "recipients": [recipient_email],
                "processingTimeMillis": 1000,
                "reportingMTA": "test-mta",
                "smtpResponse": "250 OK"
            },
            "mail": {
                "messageId": message_id,
                "destination": [recipient_email]
            }
        })
        
    elif notification_type == "Complaint":
        base_message["Message"] = json.dumps({
            "notificationType": "Complaint",
            "complaint": {
                "complainedRecipients": [
                    {
                        "emailAddress": recipient_email
                    }
                ],
                "timestamp": datetime.now().isoformat(),
                "complaintFeedbackType": "abuse"
            },
            "mail": {
                "messageId": message_id,
                "destination": [recipient_email]
            }
        })
    
    return base_message

def run_flask_server_in_background():
    """Start Flask server in the background for testing"""
    import threading
    import subprocess
    
    def run_flask():
        subprocess.run(["flask", "run", "--port=5001"], cwd="/Users/pedroitan/Desktop/DEV/emailbulk")
    
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    logger.info("Flask server started in background on port 5001")
    time.sleep(2)  # Give Flask time to start
    return flask_thread

def send_notification(notification_type, recipient_email, message_id):
    """Send a notification to the Flask application's SNS endpoint"""
    url = "http://localhost:5001/api/sns/ses-notification"
    message = create_notification_message(notification_type, recipient_email, message_id)
    
    try:
        headers = {'Content-Type': 'application/json'}
        response = requests.post(url, json=message, headers=headers)
        
        if response.status_code == 200:
            logger.info(f"Successfully sent {notification_type} notification, status code: {response.status_code}")
            return True
        else:
            logger.error(f"Failed to send {notification_type} notification, status code: {response.status_code}")
            logger.error(f"Response text: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending notification: {str(e)}")
        return False

def test_notification_updates():
    """Test if notifications properly update recipient status"""
    app = get_app()
    flask_thread = None
    
    try:
        # Try to launch Flask in background
        try:
            flask_thread = run_flask_server_in_background()
        except Exception as e:
            logger.error(f"Error starting Flask server: {str(e)}")
            logger.info("Continuing with tests assuming Flask is already running on port 5001...")
        
        with app.app_context():
            # Find a recipient to test with
            recipient = EmailRecipient.query.filter_by(status='sent').first()
            if not recipient:
                logger.error("No recipients with 'sent' status found, creating a test campaign...")
                # Create a test campaign and recipient
                campaign = EmailCampaign(
                    name=f"Test Notification Campaign {datetime.now().isoformat()}",
                    subject="Test Notification Email",
                    body_html="<p>This is a test email for notification handling.</p>",
                    body_text="This is a test email for notification handling.",
                    sender_name="Test Notification",
                    sender_email=os.environ.get('SENDER_EMAIL'),
                    scheduled_time=datetime.now(),
                    status='draft'
                )
                db.session.add(campaign)
                db.session.commit()
                
                test_recipient = EmailRecipient(
                    campaign_id=campaign.id,
                    email="test_recipient@example.com",
                    status='sent',
                    message_id=f"test-message-id-{datetime.now().timestamp()}",
                    delivery_status='sent',
                    sent_at=datetime.now()
                )
                db.session.add(test_recipient)
                db.session.commit()
                
                recipient = test_recipient
            
            # Now we have a recipient to test with
            logger.info(f"Testing with recipient: {recipient.email} (ID: {recipient.id})")
            logger.info(f"Original status: {recipient.status}, delivery_status: {recipient.delivery_status}")
            
            # Send a delivery notification first
            logger.info("Testing delivery notification...")
            if send_notification("Delivery", recipient.email, recipient.message_id):
                # Wait a bit for the notification to be processed
                time.sleep(2)
                
                # Refresh recipient from database
                db.session.refresh(recipient)
                logger.info(f"After delivery notification: status={recipient.status}, delivery_status={recipient.delivery_status}")
                
                delivery_success = recipient.delivery_status == 'delivered'
                if delivery_success:
                    logger.info("SUCCESS: Delivery status updated correctly!")
                else:
                    logger.error(f"FAILURE: Delivery status not updated correctly. Expected 'delivered', got '{recipient.delivery_status}'")
            
            # Reset status for bounce test
            recipient.delivery_status = 'sent'
            db.session.commit()
            
            # Send a bounce notification
            logger.info("Testing bounce notification...")
            if send_notification("Bounce", recipient.email, recipient.message_id):
                # Wait a bit for the notification to be processed
                time.sleep(2)
                
                # Refresh recipient from database
                db.session.refresh(recipient)
                logger.info(f"After bounce notification: status={recipient.status}, delivery_status={recipient.delivery_status}")
                
                bounce_success = recipient.delivery_status == 'bounced'
                if bounce_success:
                    logger.info("SUCCESS: Bounce status updated correctly!")
                else:
                    logger.error(f"FAILURE: Bounce status not updated correctly. Expected 'bounced', got '{recipient.delivery_status}'")
            
            return recipient.delivery_status == 'bounced'
    
    except Exception as e:
        logger.exception(f"Error during test: {str(e)}")
        return False
    finally:
        # Clean up (flask daemon thread will terminate when main thread exits)
        pass

if __name__ == "__main__":
    success = test_notification_updates()
    sys.exit(0 if success else 1)
