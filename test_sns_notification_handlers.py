#!/usr/bin/env python3
"""
Test script to verify SNS-SQS notification flow including all notification types
"""
import os
import json
import boto3
import time
import random
import string
import argparse
import requests
from dotenv import load_dotenv
from datetime import datetime, timezone

# Load environment variables
load_dotenv()

# AWS Configuration
AWS_REGION = os.getenv('AWS_REGION', 'us-east-2')
SQS_QUEUE_URL = os.getenv('SQS_QUEUE_URL')
SNS_TOPIC_ARN = os.getenv('SNS_TOPIC_ARN')
APP_URL = os.getenv('APP_URL', 'http://localhost:5000')

# Create AWS clients
sns_client = boto3.client('sns', region_name=AWS_REGION)
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
    
    return notification

def send_notification_to_sns(notification, topic_arn=None):
    """Send a notification to SNS"""
    if not topic_arn:
        topic_arn = SNS_TOPIC_ARN
    
    if not topic_arn:
        print("Error: SNS Topic ARN not specified. Set SNS_TOPIC_ARN env variable or pass it as an argument.")
        return None
    
    try:
        response = sns_client.publish(
            TopicArn=topic_arn,
            Message=json.dumps(notification),
            Subject="Test SES Notification"
        )
        message_id = response.get('MessageId')
        print(f"Sent {notification['notificationType']} notification to SNS: {message_id}")
        return message_id
    except Exception as e:
        print(f"Error sending to SNS: {str(e)}")
        return None

def send_notification_to_app(notification):
    """Send a notification directly to the app's SNS webhook endpoint"""
    url = f"{APP_URL}/api/sns/ses-notification"
    
    # Structure the notification like SNS would
    sns_message = {
        "Type": "Notification",
        "MessageId": f"test-{random.randint(1000, 9999)}",
        "TopicArn": SNS_TOPIC_ARN or "arn:aws:sns:us-east-2:123456789012:ses-notifications",
        "Subject": "Amazon SES Email Event Notification",
        "Message": json.dumps(notification),
        "Timestamp": datetime.now(timezone.utc).isoformat(),
        "SignatureVersion": "1",
        "Signature": "Test",
        "SigningCertURL": "https://sns.us-east-2.amazonaws.com/SimpleNotificationService.pem",
        "UnsubscribeURL": ""
    }
    
    try:
        response = requests.post(url, json=sns_message, headers={"Content-Type": "application/json"})
        print(f"Sent {notification['notificationType']} notification directly to app: {response.status_code}")
        print(f"Response: {response.text}")
        return response.status_code
    except Exception as e:
        print(f"Error sending to app: {str(e)}")
        return None

def check_sqs_for_notification(message_id, max_wait=60):
    """Check if a notification appears in the SQS queue"""
    if not SQS_QUEUE_URL:
        print("Error: SQS Queue URL not specified. Set SQS_QUEUE_URL env variable.")
        return False
    
    start_time = time.time()
    found = False
    
    print(f"Looking for message ID {message_id} in SQS queue...")
    
    while time.time() - start_time < max_wait and not found:
        try:
            response = sqs_client.receive_message(
                QueueUrl=SQS_QUEUE_URL,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=5,
                VisibilityTimeout=10
            )
            
            messages = response.get('Messages', [])
            if not messages:
                print("No messages found in queue, waiting...")
                continue
            
            print(f"Received {len(messages)} messages from SQS")
            
            for msg in messages:
                try:
                    body = json.loads(msg.get('Body', '{}'))
                    body_message = body.get('Message', '{}')
                    
                    if isinstance(body_message, str):
                        body_message = json.loads(body_message)
                    
                    notification_msg_id = body_message.get('mail', {}).get('messageId')
                    
                    if notification_msg_id == message_id:
                        print(f"Found matching message in SQS! Message ID: {message_id}")
                        found = True
                        
                        # Delete the message since we found it
                        receipt_handle = msg.get('ReceiptHandle')
                        sqs_client.delete_message(
                            QueueUrl=SQS_QUEUE_URL,
                            ReceiptHandle=receipt_handle
                        )
                        print(f"Deleted message from queue: {receipt_handle}")
                        break
                        
                except Exception as e:
                    print(f"Error processing message: {str(e)}")
                    continue
                    
        except Exception as e:
            print(f"Error receiving messages from SQS: {str(e)}")
            time.sleep(5)
    
    if not found:
        print(f"No matching message found in SQS after {max_wait} seconds")
    
    return found

def test_all_notification_types(direct_to_app=False):
    """Test all notification types"""
    notification_types = ["Bounce", "Complaint", "Delivery", "DeliveryDelay", "Send"]
    
    for notification_type in notification_types:
        print(f"\n===== Testing {notification_type} Notification =====")
        
        # Generate test email and message ID
        email = generate_test_email()
        message_id = generate_message_id()
        
        # Create test notification
        notification = create_test_notification(notification_type, email, message_id)
        
        # Send notification
        if direct_to_app:
            send_notification_to_app(notification)
        else:
            sns_msg_id = send_notification_to_sns(notification)
            if sns_msg_id:
                # Wait a bit for SNS to process
                time.sleep(5)
                # Check if it appears in SQS
                check_sqs_for_notification(message_id)
        
        print(f"===== Completed {notification_type} Test =====")
        
        # Add delay between tests
        time.sleep(3)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test SES Notification Handlers")
    parser.add_argument("--direct", action="store_true", help="Send notifications directly to app instead of through SNS")
    parser.add_argument("--topic-arn", help="SNS Topic ARN (overrides env variable)")
    parser.add_argument("--app-url", help="App URL (overrides env variable)")
    
    args = parser.parse_args()
    
    if args.topic_arn:
        SNS_TOPIC_ARN = args.topic_arn
    
    if args.app_url:
        APP_URL = args.app_url
    
    test_all_notification_types(direct_to_app=args.direct)
