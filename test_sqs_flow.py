"""
Test script to verify SQS notifications for SES emails

This script:
1. Sends a test email to success@simulator.amazonses.com
2. Waits for and processes SQS notifications
3. Displays the results
"""

import os
import json
import time
import logging
from email_service import SESEmailService
from sqs_handler import SQSHandler
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def test_email_and_sqs():
    """Send a test email and check SQS for notifications"""
    # Make sure SENDER_EMAIL is set in the environment, as SESEmailService reads it directly
    if not os.getenv("SENDER_EMAIL"):
        os.environ["SENDER_EMAIL"] = "noreply@bulkemailer.app"
        logger.warning(f"Set SENDER_EMAIL to {os.environ['SENDER_EMAIL']} for testing")
    
    # Set SES_CONFIGURATION_SET if not already set
    if not os.getenv("SES_CONFIGURATION_SET"):
        os.environ["SES_CONFIGURATION_SET"] = "email-bulk-scheduler-config"
        logger.info(f"Set SES_CONFIGURATION_SET to {os.environ['SES_CONFIGURATION_SET']}")
    
    # Initialize email service
    email_service = SESEmailService(
        region_name=os.getenv("AWS_REGION", "us-east-2"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
    )

    # Initialize SQS handler
    sqs_handler = SQSHandler(
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("SQS_REGION", "us-east-2")
    )
    # Set queue URL explicitly
    sqs_handler.queue_url = os.getenv("SQS_QUEUE_URL")

    # Test recipient - Amazon SES simulator address that always succeeds
    test_recipient = "success@simulator.amazonses.com"
    
    # Send test email
    logger.info(f"Sending test email to {test_recipient}")
    message_id = email_service.send_email(
        recipient=test_recipient,
        subject="SQS Test Email",
        body_html="<p>This is a test email to verify SQS notification flow.</p>",
        body_text="This is a test email to verify SQS notification flow.",
        tracking_enabled=True,
        no_return_path=False
    )
    
    if not message_id:
        logger.error("Failed to send test email - no message ID returned")
        return False
    
    logger.info(f"Test email sent! Message ID: {message_id}")
    logger.info("Waiting for SQS notifications...")
    
    # Poll SQS queue for notifications
    # Try several times with increasing backoff
    notification_received = False
    
    for attempt in range(1, 6):
        logger.info(f"Checking SQS queue (attempt {attempt}/5)...")
        
        # Poll for messages
        messages = sqs_handler.receive_messages(max_messages=10)
        
        if not messages:
            logger.info("No SQS messages received yet")
            time.sleep(5 * attempt)  # Increasing backoff
            continue
            
        logger.info(f"Received {len(messages)} SQS messages")
        
        # Process messages
        for message in messages:
            try:
                receipt_handle = message.get('ReceiptHandle')
                
                # Parse message body
                raw_body = message.get('Body', '{}')
                if not raw_body or not raw_body.strip():
                    logger.warning("Empty message body")
                    continue
                    
                body = json.loads(raw_body)
                
                if 'Message' in body:
                    raw_message = body.get('Message')
                    sns_message = json.loads(raw_message)
                    
                    # Check message type
                    notification_type = sns_message.get('notificationType') or sns_message.get('eventType')
                    logger.info(f"Received notification type: {notification_type}")
                    
                    # Display message details
                    logger.info(f"Notification details: {json.dumps(sns_message, indent=2)}")
                    notification_received = True
                
                # Delete message after processing
                sqs_handler.delete_message(receipt_handle)
                
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
    
    if notification_received:
        logger.info("✅ SUCCESS: Email sent and SQS notification received!")
        return True
    else:
        logger.warning("❌ TEST INCOMPLETE: Email sent but no SQS notification received within timeout")
        logger.info("This could be due to SQS/SNS configuration or delay in notification delivery")
        return False

if __name__ == "__main__":
    logger.info("Starting SQS notification test...")
    test_email_and_sqs()
