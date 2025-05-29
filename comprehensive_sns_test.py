import boto3
import json
import time
import os
import requests
from dotenv import load_dotenv
import logging
import uuid

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# AWS configuration
aws_region = os.getenv('AWS_REGION', 'us-east-2')
aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
topic_arn = os.getenv('SNS_TOPIC_ARN', 'arn:aws:sns:us-east-2:109869386849:ses-email-bulk-scheduler-config-notifications')
sender_email = os.getenv('SENDER_EMAIL', 'test@example.com')
app_url = os.getenv('APP_URL', 'https://emailbulk-web.onrender.com')

# Create AWS SNS client
sns_client = boto3.client('sns', region_name=aws_region,
                         aws_access_key_id=aws_access_key,
                         aws_secret_access_key=aws_secret_key)

def create_bounce_notification():
    """Create a test bounce notification"""
    message_id = f"test-bounce-{uuid.uuid4()}"
    return {
        "notificationType": "Bounce",
        "bounce": {
            "bounceType": "Permanent",
            "bounceSubType": "General",
            "bouncedRecipients": [
                {
                    "emailAddress": "bounce-test@example.com",
                    "action": "failed",
                    "status": "5.1.1",
                    "diagnosticCode": "Test bounce message"
                }
            ],
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
            "feedbackId": f"feedback-bounce-{uuid.uuid4()}"
        },
        "mail": {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(time.time() - 300)),
            "messageId": message_id,
            "source": sender_email,
            "sourceArn": f"arn:aws:ses:us-east-2:109869386849:identity/{sender_email}",
            "destination": ["bounce-test@example.com"]
        }
    }

def create_complaint_notification():
    """Create a test complaint notification"""
    message_id = f"test-complaint-{uuid.uuid4()}"
    return {
        "notificationType": "Complaint",
        "complaint": {
            "complainedRecipients": [
                {
                    "emailAddress": "complaint-test@example.com"
                }
            ],
            "complaintFeedbackType": "abuse",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
            "feedbackId": f"feedback-complaint-{uuid.uuid4()}"
        },
        "mail": {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(time.time() - 300)),
            "messageId": message_id,
            "source": sender_email,
            "sourceArn": f"arn:aws:ses:us-east-2:109869386849:identity/{sender_email}",
            "destination": ["complaint-test@example.com"]
        }
    }

def create_delivery_notification():
    """Create a test delivery notification"""
    message_id = f"test-delivery-{uuid.uuid4()}"
    return {
        "notificationType": "Delivery",
        "delivery": {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
            "processingTimeMillis": 500,
            "recipients": ["delivery-test@example.com"],
            "smtpResponse": "250 2.0.0 OK",
            "reportingMTA": "a8-50.smtp-out.amazonses.com"
        },
        "mail": {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(time.time() - 300)),
            "messageId": message_id,
            "source": sender_email,
            "sourceArn": f"arn:aws:ses:us-east-2:109869386849:identity/{sender_email}",
            "destination": ["delivery-test@example.com"]
        }
    }

def send_sns_notification(notification, notification_type):
    """Send a test notification to SNS"""
    try:
        # Publish message to SNS topic
        response = sns_client.publish(
            TopicArn=topic_arn,
            Message=json.dumps(notification),
            MessageStructure='string'
        )
        
        message_id = response.get('MessageId')
        logger.info(f"✅ Successfully published {notification_type} notification to SNS: {message_id}")
        return message_id
        
    except Exception as e:
        logger.error(f"❌ Error publishing {notification_type} notification to SNS: {str(e)}")
        return None

def attempt_direct_webhook_delivery(notification, notification_type):
    """Try to deliver notification directly to webhook endpoint"""
    try:
        # Create SNS-style message wrapper
        sns_message = {
            "Type": "Notification",
            "Message": json.dumps(notification)
        }
        
        # Webhook endpoint URL
        webhook_url = f"{app_url}/api/sns/ses-notification"
        
        # Send POST request to webhook
        logger.info(f"Attempting direct webhook delivery to: {webhook_url}")
        response = requests.post(
            webhook_url,
            json=sns_message,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            logger.info(f"✅ Successfully delivered {notification_type} notification directly to webhook: {response.status_code}")
            logger.debug(f"Response content: {response.text[:200]}")
            return True
        else:
            logger.error(f"❌ Failed to deliver {notification_type} notification to webhook: {response.status_code}")
            logger.error(f"Response content: {response.text[:200]}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error delivering {notification_type} notification to webhook: {str(e)}")
        return False

def run_comprehensive_test():
    """Run a comprehensive test of SNS notifications"""
    logger.info("=== STARTING COMPREHENSIVE SNS NOTIFICATION TEST ===")
    
    # Test all notification types
    notification_types = ["bounce", "complaint", "delivery"]
    
    for notification_type in notification_types:
        logger.info(f"\n=== TESTING {notification_type.upper()} NOTIFICATION ===")
        
        # Create the appropriate notification
        if notification_type == "bounce":
            notification = create_bounce_notification()
        elif notification_type == "complaint":
            notification = create_complaint_notification()
        else:  # delivery
            notification = create_delivery_notification()
        
        # Send via SNS
        message_id = send_sns_notification(notification, notification_type)
        
        if message_id:
            logger.info(f"Waiting 5 seconds for SNS to process {notification_type} notification...")
            time.sleep(5)
            
            # Optionally, try direct webhook delivery too
            logger.info(f"Attempting direct webhook delivery for {notification_type} notification...")
            direct_success = attempt_direct_webhook_delivery(notification, notification_type)
            
            if direct_success:
                logger.info(f"✅ {notification_type.capitalize()} notification test completed successfully via direct webhook")
            else:
                logger.warning(f"⚠️ Direct webhook delivery of {notification_type} notification failed - check app logs")
        
        # Pause between notification types
        time.sleep(2)
    
    logger.info("\n=== COMPREHENSIVE SNS NOTIFICATION TEST COMPLETE ===")
    logger.info("Check your application logs to see if notifications were processed correctly!")
    logger.info("Remember: Critical notifications (bounce, complaint) should bypass your rate limiter.")

if __name__ == "__main__":
    run_comprehensive_test()
