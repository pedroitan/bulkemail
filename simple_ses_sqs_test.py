"""
Simple test script to send an email to SES simulator and check SQS notifications

This is a stripped-down, focused test that:
1. Sends a single email to success@simulator.amazonses.com via Amazon SES
2. Checks the SQS queue for notifications
"""

import os
import json
import time
import logging
import boto3
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def send_ses_email():
    """Send a test email using Amazon SES directly via boto3"""
    # Get configuration from environment
    aws_region = os.getenv('AWS_REGION') or 'us-east-2'
    sender_email = os.getenv('SENDER_EMAIL') or 'vendo147@vendo147.com'  # Using the email from the logs
    configuration_set = os.getenv('SES_CONFIGURATION_SET') or 'email-bulk-scheduler-config'
    
    logger.info(f"Using sender email: {sender_email}")
    logger.info(f"Using SES region: {aws_region}")
    logger.info(f"Using configuration set: {configuration_set}")
    
    # Create SES client
    ses_client = boto3.client(
        'ses',
        region_name=aws_region,
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
    )
    
    # Test recipient - Amazon SES simulator address that always succeeds
    test_recipient = "success@simulator.amazonses.com"
    
    try:
        # Send email using SES
        response = ses_client.send_email(
            Source=sender_email,
            Destination={
                'ToAddresses': [test_recipient]
            },
            Message={
                'Subject': {
                    'Data': 'SES-SQS Test Email'
                },
                'Body': {
                    'Text': {
                        'Data': 'This is a test email to verify SQS notifications.'
                    },
                    'Html': {
                        'Data': '<p>This is a test email to verify SQS notifications.</p>'
                    }
                }
            },
            ConfigurationSetName=configuration_set,
            ReturnPath=sender_email
        )
        
        message_id = response.get('MessageId')
        logger.info(f"Email sent successfully! Message ID: {message_id}")
        return message_id
    
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        return None

def check_sqs_notifications():
    """Check SQS queue for SES notifications"""
    # Get configuration from environment
    aws_region = os.getenv('SQS_REGION') or os.getenv('AWS_REGION') or 'us-east-2'
    queue_url = os.getenv('SQS_QUEUE_URL')
    
    if not queue_url:
        logger.error("SQS_QUEUE_URL not set in environment variables!")
        return False
        
    logger.info(f"Using SQS region: {aws_region}")
    logger.info(f"Using queue URL: {queue_url}")
    
    # Create SQS client
    sqs_client = boto3.client(
        'sqs',
        region_name=aws_region,
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
    )
    
    # Try to receive messages several times with increasing backoff
    notification_received = False
    
    for attempt in range(1, 6):
        logger.info(f"Checking SQS queue (attempt {attempt}/5)...")
        
        try:
            # Receive messages
            response = sqs_client.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=5
            )
            
            messages = response.get('Messages', [])
            
            if not messages:
                logger.info("No SQS messages received yet")
                time.sleep(5 * attempt)  # Increasing backoff
                continue
                
            logger.info(f"Received {len(messages)} SQS messages")
            
            # Process messages
            for message in messages:
                receipt_handle = message.get('ReceiptHandle')
                
                try:
                    # Parse message body
                    body = json.loads(message.get('Body', '{}'))
                    
                    if 'Message' in body:
                        sns_message = json.loads(body.get('Message', '{}'))
                        
                        # Check message type
                        notification_type = sns_message.get('notificationType') or sns_message.get('eventType')
                        logger.info(f"Received notification type: {notification_type}")
                        
                        # Display relevant parts of the message
                        if notification_type == 'Delivery':
                            delivery_info = sns_message.get('delivery', {})
                            timestamp = delivery_info.get('timestamp', 'unknown')
                            recipients = delivery_info.get('recipients', [])
                            logger.info(f"Delivery notification at {timestamp} for recipients: {recipients}")
                        else:
                            logger.info(f"Notification details: {json.dumps(sns_message, indent=2)}")
                            
                        notification_received = True
                    
                    # Delete the message
                    sqs_client.delete_message(
                        QueueUrl=queue_url,
                        ReceiptHandle=receipt_handle
                    )
                    
                except json.JSONDecodeError:
                    logger.warning(f"Received message with invalid JSON: {message.get('Body', '')[:100]}...")
                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error checking SQS queue: {str(e)}")
    
    return notification_received

if __name__ == "__main__":
    logger.info("Starting SES/SQS integration test...")
    
    # Step 1: Send a test email
    message_id = send_ses_email()
    
    if not message_id:
        logger.error("Failed to send test email. Aborting test.")
        exit(1)
    
    # Step 2: Check for SQS notifications
    logger.info("Waiting for SQS notifications...")
    notification_received = check_sqs_notifications()
    
    # Report test results
    if notification_received:
        logger.info("✅ SUCCESS: Email sent and SQS notification received!")
    else:
        logger.warning("⚠️ PARTIAL SUCCESS: Email sent but no SQS notification received within timeout")
        logger.info("This could be due to SQS/SNS configuration or delay in notification delivery")
