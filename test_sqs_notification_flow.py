#!/usr/bin/env python3
"""
Test SQS notification flow by directly sending test messages to SQS
and then running the SQS processor to verify they're handled correctly.
"""
import os
import json
import boto3
import time
import random
import string
from datetime import datetime, timezone
from dotenv import load_dotenv
import logging
import subprocess

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# AWS Configuration
AWS_REGION = os.getenv('AWS_REGION', 'us-east-2')
SQS_QUEUE_URL = os.getenv('SQS_QUEUE_URL')

if not SQS_QUEUE_URL:
    raise ValueError("SQS_QUEUE_URL environment variable must be set")

# Create SQS client
sqs_client = boto3.client('sqs', region_name=AWS_REGION)

def generate_test_email():
    """Generate a random test email address"""
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"test-{random_str}@example.com"

def generate_message_id():
    """Generate a fake message ID"""
    return f"message-{int(time.time())}-{random.randint(1000, 9999)}"

def create_test_notification(notification_type, email=None, message_id=None):
    """Create a test notification for the specified type"""
    if not email:
        email = generate_test_email()
    if not message_id:
        message_id = generate_message_id()
    
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Common mail object structure
    mail_obj = {
        "timestamp": timestamp,
        "messageId": message_id,
        "source": "noreply@yourdomain.com",
        "sourceArn": "arn:aws:ses:us-east-2:123456789012:identity/yourdomain.com",
        "sourceIp": "192.0.2.0",
        "sendingAccountId": "123456789012",
        "destination": [email],
        "headersTruncated": False,
        "headers": []
    }
    
    # Create notification based on type
    notification = {
        "notificationType": notification_type,
        "mail": mail_obj
    }
    
    if notification_type == "Bounce":
        notification["bounce"] = {
            "bounceType": "Permanent",
            "bounceSubType": "General",
            "bouncedRecipients": [{"emailAddress": email, "diagnosticCode": "Test bounce"}],
            "timestamp": timestamp,
            "feedbackId": f"feedback-{random.randint(1000, 9999)}"
        }
    elif notification_type == "Complaint":
        notification["complaint"] = {
            "complainedRecipients": [{"emailAddress": email}],
            "timestamp": timestamp,
            "feedbackId": f"feedback-{random.randint(1000, 9999)}",
            "complaintFeedbackType": "abuse"
        }
    elif notification_type == "Delivery":
        notification["delivery"] = {
            "timestamp": timestamp,
            "processingTimeMillis": 1000,
            "recipients": [email],
            "smtpResponse": "250 OK"
        }
    elif notification_type == "DeliveryDelay":
        notification["deliveryDelay"] = {
            "delayType": "MailboxFull",
            "timestamp": timestamp,
            "delayedRecipients": [{"emailAddress": email}]
        }
    elif notification_type == "Send":
        # Send has a simpler structure, just the mail object and notificationType
        pass
    
    return notification, message_id, email

def create_sns_formatted_message(notification):
    """Format a notification as an SNS message for SQS"""
    return {
        "Type": "Notification",
        "MessageId": f"test-{random.randint(1000, 9999)}",
        "TopicArn": "arn:aws:sns:us-east-2:123456789012:ses-notifications",
        "Subject": "Amazon SES Email Event Notification",
        "Message": json.dumps(notification),
        "Timestamp": datetime.now(timezone.utc).isoformat(),
        "SignatureVersion": "1",
        "Signature": "TestSignature",
        "SigningCertURL": "https://sns.us-east-2.amazonaws.com/SimpleNotificationService.pem",
        "UnsubscribeURL": ""
    }

def send_test_notification_to_sqs(notification_type):
    """Create and send a test notification to SQS"""
    notification, message_id, email = create_test_notification(notification_type)
    sns_message = create_sns_formatted_message(notification)
    
    try:
        response = sqs_client.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=json.dumps(sns_message)
        )
        sqs_message_id = response.get('MessageId')
        logger.info(f"Sent {notification_type} notification to SQS: {sqs_message_id}")
        logger.info(f"Test email: {email}, Message ID: {message_id}")
        return sqs_message_id, message_id, email
    except Exception as e:
        logger.error(f"Error sending to SQS: {str(e)}")
        return None, message_id, email

def run_sqs_processor():
    """Run the SQS processor to handle the test messages"""
    logger.info("Running SQS processor...")
    try:
        subprocess.run(["python", "sqs_jobs.py"], check=True)
        logger.info("SQS processor completed")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running SQS processor: {str(e)}")
        return False

def test_all_notification_types():
    """Test all notification types"""
    notification_types = ["Bounce", "Complaint", "Delivery", "DeliveryDelay", "Send"]
    results = {}
    
    for notification_type in notification_types:
        logger.info(f"\n===== Testing {notification_type} Notification =====")
        
        # Send test notification to SQS
        sqs_message_id, message_id, email = send_test_notification_to_sqs(notification_type)
        
        if sqs_message_id:
            # Record the test case details
            results[notification_type] = {
                "sqs_message_id": sqs_message_id,
                "ses_message_id": message_id,
                "email": email,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Successfully sent {notification_type} notification to SQS")
        else:
            logger.error(f"Failed to send {notification_type} notification to SQS")
        
        # Small delay between messages
        time.sleep(1)
    
    # Process all the test messages
    if results:
        logger.info("\n===== Processing Test Messages =====")
        success = run_sqs_processor()
        
        if success:
            logger.info("All test messages processed successfully")
        else:
            logger.error("Error processing test messages")
    
    return results

if __name__ == "__main__":
    logger.info("Starting SQS notification flow test")
    results = test_all_notification_types()
    
    logger.info("\n===== Test Summary =====")
    for notification_type, details in results.items():
        logger.info(f"{notification_type}: Message ID {details['ses_message_id']} for {details['email']}")
    
    logger.info("\nTest complete. Check the application logs for verification of notification processing.")
