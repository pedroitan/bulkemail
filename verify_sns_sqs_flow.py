import boto3
import json
import time
import os
import uuid
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# AWS configuration
aws_region = os.getenv('AWS_REGION', 'us-east-2')
aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
topic_arn = os.getenv('SNS_TOPIC_ARN', 'arn:aws:sns:us-east-2:109869386849:ses-email-bulk-scheduler-config-notifications')
sqs_queue_url = os.getenv('SQS_QUEUE_URL')
sender_email = os.getenv('SENDER_EMAIL')

# Create AWS clients
sns_client = boto3.client('sns', 
                         region_name=aws_region,
                         aws_access_key_id=aws_access_key,
                         aws_secret_access_key=aws_secret_key)

sqs_client = boto3.client('sqs', 
                         region_name=aws_region,
                         aws_access_key_id=aws_access_key,
                         aws_secret_access_key=aws_secret_key)

def send_test_sns_notification(notification_type):
    """Send a test notification to SNS"""
    message_id = f"test-{notification_type}-{uuid.uuid4()}"
    
    # Create notification based on type
    if notification_type == "bounce":
        notification = {
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
    elif notification_type == "complaint":
        notification = {
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
    else:  # delivery
        notification = {
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

def check_sqs_for_messages(wait_time=30, max_attempts=3):
    """Check SQS queue for messages with multiple attempts"""
    logger.info(f"Checking SQS queue for messages (will wait up to {wait_time*max_attempts} seconds)...")
    
    for attempt in range(1, max_attempts + 1):
        logger.info(f"Attempt {attempt}/{max_attempts} to receive messages...")
        
        try:
            # Receive messages from SQS queue with longer wait time
            response = sqs_client.receive_message(
                QueueUrl=sqs_queue_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=wait_time,  # Long polling
                AttributeNames=['All'],
                MessageAttributeNames=['All']
            )
            
            messages = response.get('Messages', [])
            
            if messages:
                logger.info(f"✅ Received {len(messages)} message(s) from SQS queue")
                
                for i, message in enumerate(messages):
                    message_id = message.get('MessageId')
                    receipt_handle = message.get('ReceiptHandle')
                    body = message.get('Body')
                    
                    logger.info(f"Message {i+1}:")
                    logger.info(f"  MessageId: {message_id}")
                    
                    # Parse message body (SNS notification wrapped in SQS message)
                    try:
                        body_json = json.loads(body)
                        sns_message = body_json.get('Message', '')
                        
                        if sns_message:
                            try:
                                sns_message_json = json.loads(sns_message)
                                notification_type = sns_message_json.get('notificationType', 'Unknown')
                                logger.info(f"  NotificationType: {notification_type}")
                                
                                # Delete message after processing
                                sqs_client.delete_message(
                                    QueueUrl=sqs_queue_url,
                                    ReceiptHandle=receipt_handle
                                )
                                logger.info(f"  Message deleted from queue")
                            except json.JSONDecodeError:
                                logger.warning(f"  SNS message is not valid JSON: {sns_message[:100]}...")
                        else:
                            logger.warning(f"  No SNS message found in body")
                    except json.JSONDecodeError:
                        logger.warning(f"  Message body is not valid JSON: {body[:100]}...")
                
                return True
            else:
                logger.warning(f"No messages found in SQS queue on attempt {attempt}")
                
                if attempt < max_attempts:
                    logger.info(f"Waiting for more attempts...")
                else:
                    logger.warning("Max attempts reached without finding messages")
                    return False
        
        except Exception as e:
            logger.error(f"❌ Error receiving messages from SQS queue: {str(e)}")
            return False
    
    return False

def verify_sns_sqs_flow():
    """Verify the entire SNS to SQS notification flow"""
    logger.info("=== VERIFYING SNS TO SQS NOTIFICATION FLOW ===")
    
    # Test all notification types (prioritizing critical ones)
    notification_types = ["bounce", "complaint", "delivery"]
    sent_messages = []
    
    for notification_type in notification_types:
        logger.info(f"\n=== SENDING {notification_type.upper()} NOTIFICATION ===")
        message_id = send_test_sns_notification(notification_type)
        
        if message_id:
            sent_messages.append((notification_type, message_id))
    
    # Wait a bit for SNS to deliver messages to SQS
    if sent_messages:
        logger.info("\nWaiting 10 seconds for SNS to deliver messages to SQS...")
        time.sleep(10)
        
        # Check SQS for messages
        logger.info("\n=== CHECKING SQS FOR MESSAGES ===")
        messages_received = check_sqs_for_messages(wait_time=10, max_attempts=3)
        
        if messages_received:
            logger.info("\n✅ VERIFICATION SUCCESSFUL: SNS to SQS flow is working!")
            logger.info("Messages are properly flowing from SNS to SQS")
            
            # Highlight token bucket rate limiter
            logger.info("\nYour token bucket rate limiter will now properly manage these notifications:")
            logger.info("- Critical notifications (bounce, complaint) should bypass rate limiting")
            logger.info("- Regular notifications (delivery) will be subject to rate limits")
            logger.info("- This prevents app crashes during large campaigns with 3,000+ emails")
            
            return True
        else:
            logger.warning("\n⚠️ VERIFICATION INCOMPLETE: No messages found in SQS queue")
            logger.warning("This may indicate that messages are still not flowing from SNS to SQS")
            logger.warning("Possible issues:")
            logger.warning("1. SQS policy might not be fully propagated yet (can take a few minutes)")
            logger.warning("2. SNS subscription may need to be refreshed")
            logger.warning("3. There might be another permission issue")
            
            return False
    else:
        logger.error("\n❌ VERIFICATION FAILED: Could not send test notifications to SNS")
        return False

if __name__ == "__main__":
    verify_sns_sqs_flow()
