"""
SQS Handler Module

This module provides functionality for AWS SQS queue operations to handle
SES email notifications. It implements a pattern that works with Render's 
free tier by offloading notification processing to an SQS queue.
"""

import boto3
import json
import logging
import time
from flask import current_app

logger = logging.getLogger(__name__)

class SQSHandler:
    """
    Handles SQS operations for SES notifications with lazy initialization pattern.
    
    This class manages the interaction between the application and an AWS SQS queue
    that serves as a buffer for SES notifications. It implements a lazy initialization
    pattern that only initializes the boto3 client when actually needed.
    
    The primary purpose is to prevent server overload during large email campaigns 
    (up to 40k emails) by offloading notification processing to a queue.
    """

    def __init__(self, aws_access_key_id=None, aws_secret_access_key=None, region_name=None):
        """
        Initialize the SQS handler with lazy loading
        
        Args:
            aws_access_key_id: Optional AWS access key, defaults to app config
            aws_secret_access_key: Optional AWS secret key, defaults to app config
            region_name: Optional AWS region, defaults to app config
        """
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.region_name = region_name
        self.client = None
        self.queue_url = None
        self.logger = logging.getLogger(__name__)
    
    def _ensure_client(self):
        """
        Ensures the boto3 SQS client is initialized when needed - lazy initialization
        """
        if self.client is None:
            try:
                # In Flask application context, get from app config
                self.aws_access_key_id = self.aws_access_key_id or current_app.config['AWS_ACCESS_KEY_ID']
                self.aws_secret_access_key = self.aws_secret_access_key or current_app.config['AWS_SECRET_ACCESS_KEY']
                
                # Use SQS_REGION if available, otherwise fall back to AWS_REGION
                self.region_name = self.region_name or current_app.config.get('SQS_REGION') or current_app.config['AWS_REGION']
                self.logger.info(f"Using SQS region: {self.region_name}")
                
                # Get queue URL from config
                self.queue_url = current_app.config.get('SQS_QUEUE_URL')
                if not self.queue_url:
                    self.logger.warning("SQS_QUEUE_URL not found in config. SQS features will be disabled.")
            
            except RuntimeError:
                # Not in Flask app context, use provided credentials
                self.logger.warning("Not in Flask application context, using provided credentials")
                if not all([self.aws_access_key_id, self.aws_secret_access_key, self.region_name]):
                    self.logger.error("Missing AWS credentials for SQS client")
                    return
            
            # Create the actual boto3 client
            self.client = boto3.client(
                'sqs',
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.region_name
            )
            self.logger.info("SQS client created successfully")
    
    def send_message(self, message_body):
        """
        Send a message to the SQS queue
        
        Args:
            message_body: Dict or string to send to SQS
            
        Returns:
            Message ID if successful, None otherwise
        """
        self._ensure_client()
        
        if not self.client or not self.queue_url:
            self.logger.warning("SQS client or queue URL not available. Message not sent.")
            return None
        
        try:
            # Convert dict to JSON string if needed
            if isinstance(message_body, dict):
                message_body = json.dumps(message_body)
                
            response = self.client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=message_body
            )
            message_id = response.get('MessageId')
            self.logger.info(f"Message sent to SQS queue: {message_id}")
            return message_id
            
        except Exception as e:
            self.logger.error(f"Error sending message to SQS: {str(e)}")
            return None
    
    def receive_messages(self, max_messages=10, wait_time=1, visibility_timeout=60):
        """
        Receive messages from the SQS queue
        
        Args:
            max_messages: Maximum number of messages to receive (1-10)
            wait_time: How long to wait for messages (0-20 seconds)
            visibility_timeout: How long to hide the message (seconds)
            
        Returns:
            List of messages or empty list if none available
        """
        self._ensure_client()
        
        if not self.client or not self.queue_url:
            self.logger.warning("SQS client or queue URL not available. Cannot receive messages.")
            return []
        
        try:
            response = self.client.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=max_messages,
                WaitTimeSeconds=wait_time,
                VisibilityTimeout=visibility_timeout,
                AttributeNames=['All'],
                MessageAttributeNames=['All']
            )
            
            messages = response.get('Messages', [])
            self.logger.info(f"Received {len(messages)} messages from SQS queue")
            return messages
            
        except Exception as e:
            self.logger.error(f"Error receiving messages from SQS: {str(e)}")
            return []
    
    def delete_message(self, receipt_handle):
        """
        Delete a message from the queue after processing
        
        Args:
            receipt_handle: The receipt handle of the message to delete
            
        Returns:
            True if successful, False otherwise
        """
        self._ensure_client()
        
        if not self.client or not self.queue_url:
            self.logger.warning("SQS client or queue URL not available. Cannot delete message.")
            return False
        
        try:
            self.client.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle
            )
            self.logger.info(f"Message deleted from SQS queue")
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting message from SQS: {str(e)}")
            return False
    
    def create_queue(self, queue_name):
        """
        Create a new SQS queue
        
        Args:
            queue_name: Name of the queue to create
            
        Returns:
            Queue URL if successful, None otherwise
        """
        self._ensure_client()
        
        if not self.client:
            self.logger.warning("SQS client not available. Cannot create queue.")
            return None
        
        try:
            response = self.client.create_queue(
                QueueName=queue_name,
                Attributes={
                    'VisibilityTimeout': '60',  # 1 minute
                    'MessageRetentionPeriod': '86400',  # 1 day
                    'ReceiveMessageWaitTimeSeconds': '10'  # Long polling
                }
            )
            
            self.queue_url = response.get('QueueUrl')
            self.logger.info(f"SQS queue created: {self.queue_url}")
            return self.queue_url
            
        except Exception as e:
            self.logger.error(f"Error creating SQS queue: {str(e)}")
            return None
