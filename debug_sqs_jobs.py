#!/usr/bin/env python3
"""
Enhanced debug script to test SNS-SQS notification processing
with detailed logging
"""
import os
import json
import boto3
import time
import logging
from dotenv import load_dotenv
from datetime import datetime

# Configure detailed logging
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Ensure boto3 logging is enabled
boto3_logger = logging.getLogger('boto3')
boto3_logger.setLevel(logging.DEBUG)
botocore_logger = logging.getLogger('botocore')
botocore_logger.setLevel(logging.DEBUG)

# Load environment variables
load_dotenv()

# AWS Configuration
AWS_REGION = os.getenv('AWS_REGION', 'us-east-2')
SQS_QUEUE_URL = os.getenv('SQS_QUEUE_URL')

# Create SQS client
sqs = boto3.client('sqs', region_name=AWS_REGION)

def receive_messages():
    """Receive messages from SQS queue with detailed logging"""
    logger.info(f"Attempting to receive messages from queue: {SQS_QUEUE_URL}")
    
    try:
        # Check if there are any messages in the queue
        response = sqs.receive_message(
            QueueUrl=SQS_QUEUE_URL,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=10,
            AttributeNames=['All'],
            MessageAttributeNames=['All']
        )
        
        messages = response.get('Messages', [])
        logger.info(f"Received {len(messages)} messages from SQS queue")
        
        if not messages:
            logger.warning("No messages found in queue!")
            return
        
        # Process each message
        for i, message in enumerate(messages, 1):
            logger.info(f"Processing message {i}/{len(messages)}")
            receipt_handle = message.get('ReceiptHandle')
            body = message.get('Body', '{}')
            
            try:
                logger.debug(f"Message body: {body[:500]}...")
                
                # Try to parse the message body as JSON
                body_json = json.loads(body)
                logger.debug(f"Message type: {body_json.get('Type')}")
                
                # For SNS notifications, parse the Message field
                if body_json.get('Type') == 'Notification':
                    message_str = body_json.get('Message', '{}')
                    logger.debug(f"SNS Message content: {message_str[:500]}...")
                    
                    try:
                        # Parse the SNS message content
                        notification = json.loads(message_str)
                        notification_type = notification.get('notificationType')
                        
                        logger.info(f"SNS notification type: {notification_type}")
                        logger.debug(f"Notification details: {json.dumps(notification)[:500]}...")
                        
                        # Delete the message from the queue
                        logger.info(f"Deleting message with receipt handle: {receipt_handle[:20]}...")
                        sqs.delete_message(
                            QueueUrl=SQS_QUEUE_URL,
                            ReceiptHandle=receipt_handle
                        )
                        logger.info(f"Successfully deleted message {i}")
                    except json.JSONDecodeError:
                        logger.error(f"Could not parse SNS Message as JSON: {message_str[:100]}")
                        continue
                else:
                    logger.warning(f"Unexpected message format: {body_json.get('Type')}")
            except json.JSONDecodeError:
                logger.error(f"Could not parse message body as JSON: {body[:100]}")
                continue
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}", exc_info=True)
                continue

    except Exception as e:
        logger.error(f"Error receiving messages: {str(e)}", exc_info=True)

if __name__ == "__main__":
    logger.info("Starting enhanced SQS message debug...")
    receive_messages()
    logger.info("Debug complete.")
