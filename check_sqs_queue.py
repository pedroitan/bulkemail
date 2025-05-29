"""
Simple script to check for any messages currently in the SQS queue
"""

import os
import json
import logging
import boto3
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def check_sqs_queue():
    """Check for any messages in the SQS queue"""
    # Get configuration from environment
    aws_region = os.getenv('SQS_REGION') or os.getenv('AWS_REGION') or 'us-east-2'
    queue_url = os.getenv('SQS_QUEUE_URL')
    
    if not queue_url:
        logger.error("SQS_QUEUE_URL not set in environment variables!")
        return
        
    logger.info(f"Using SQS region: {aws_region}")
    logger.info(f"Using queue URL: {queue_url}")
    
    # Create SQS client
    sqs_client = boto3.client(
        'sqs',
        region_name=aws_region,
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
    )
    
    try:
        # Get queue attributes to check message count
        queue_attrs = sqs_client.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=['ApproximateNumberOfMessages', 'ApproximateNumberOfMessagesNotVisible']
        )
        
        attributes = queue_attrs.get('Attributes', {})
        message_count = int(attributes.get('ApproximateNumberOfMessages', 0))
        invisible_count = int(attributes.get('ApproximateNumberOfMessagesNotVisible', 0))
        
        logger.info(f"Queue status: {message_count} visible messages, {invisible_count} in-flight messages")
        
        # Try to receive any available messages
        response = sqs_client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=10,
            VisibilityTimeout=0  # Don't hide the message after receiving
        )
        
        messages = response.get('Messages', [])
        if not messages:
            logger.info("No messages available to receive at this time")
            return
            
        logger.info(f"Received {len(messages)} SQS messages for inspection")
        
        # Process and display messages without deleting them
        for i, message in enumerate(messages):
            logger.info(f"Message {i+1}:")
            
            try:
                # Parse message body
                body = json.loads(message.get('Body', '{}'))
                
                if 'Message' in body:
                    try:
                        sns_message = json.loads(body.get('Message', '{}'))
                        notification_type = sns_message.get('notificationType') or sns_message.get('eventType')
                        logger.info(f"  Type: {notification_type}")
                        
                        if notification_type == 'Delivery':
                            delivery = sns_message.get('delivery', {})
                            recipients = delivery.get('recipients', [])
                            timestamp = delivery.get('timestamp')
                            logger.info(f"  Delivery to: {recipients}")
                            logger.info(f"  Timestamp: {timestamp}")
                        else:
                            mail = sns_message.get('mail', {})
                            destination = mail.get('destination', [])
                            timestamp = mail.get('timestamp')
                            logger.info(f"  For: {destination}")
                            logger.info(f"  Timestamp: {timestamp}")
                    except json.JSONDecodeError:
                        logger.warning("  SNS message is not valid JSON")
                else:
                    logger.info(f"  Not an SNS notification: {body}")
            except json.JSONDecodeError:
                logger.warning(f"  Message body is not valid JSON: {message.get('Body', '')[:100]}")
            
            logger.info("---")
    
    except Exception as e:
        logger.error(f"Error checking SQS queue: {str(e)}")

if __name__ == "__main__":
    logger.info("Checking SQS queue for messages...")
    check_sqs_queue()
