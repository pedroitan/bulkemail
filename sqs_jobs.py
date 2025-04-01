"""
SQS background job for handling AWS SNS notifications queued in SQS

This module provides a standalone function for processing SQS messages
containing SNS notifications. It is designed to be used with APScheduler
in a way that avoids serialization issues.
"""

import json
import time
import logging

# Enhanced debugging configuration
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

# Configure logging for detailed debug output
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.addHandler(console_handler)

def process_sqs_queue_job():
    """
    Process SQS messages at a controlled rate compatible with Render's free tier
    
    This function properly handles Flask application context to avoid APScheduler serialization issues
    that occur when passing Flask app objects directly to job functions.
    """
    # Import Flask and app-specific dependencies inside the function to avoid circular imports
    import sys
    from flask import Flask
    
    # Need to get a reference to the app but can't use current_app outside app context
    try:
        # Try to get the app from app.py which should be imported by now
        app_module = sys.modules.get('app')
        if app_module and hasattr(app_module, 'app'):
            app = app_module.app
        else:
            # Fallback method - dynamically import the app
            from app import app
            
        # Create an application context for this thread
        with app.app_context():
            try:
                # Process up to 10 messages per minute
                sqs_handler = app.get_sqs_handler()
                
                logger.debug("==== SQS QUEUE PROCESSING STARTED ====")
                logger.debug(f"SQS Queue URL: {app.config.get('SQS_QUEUE_URL')}")
                logger.debug(f"AWS Region: {app.config.get('AWS_REGION', 'us-east-2')}")
                
                messages = sqs_handler.receive_messages(max_messages=10)
                
                if not messages:
                    logger.debug("No messages found in SQS queue")
                    return
                    
                app.logger.info(f"Processing {len(messages)} SQS messages from scheduled job")
                logger.debug(f"Raw messages received from SQS: {json.dumps([{'MessageId': m.get('MessageId'), 'MD5': m.get('MD5OfBody')} for m in messages], indent=2)}")
                processed = 0
        
                for message in messages:
                    try:
                        # Extract and process the SNS message
                        receipt_handle = message['ReceiptHandle']
                        
                        # Debug the raw message
                        logger.debug(f"Processing message ID: {message.get('MessageId')}")
                        logger.debug(f"Message attributes: {json.dumps(message.get('Attributes', {}), indent=2)}")
                        
                        # Safely parse the message body
                        raw_body = message.get('Body', '{}')
                        if not raw_body or not raw_body.strip():
                            app.logger.warning("Received empty message body, skipping")
                            sqs_handler.delete_message(receipt_handle)
                            continue
                            
                        try:
                            body = json.loads(raw_body)
                        except json.JSONDecodeError as json_err:
                            app.logger.warning(f"Invalid JSON in message body: {str(json_err)}")
                            app.logger.debug(f"Raw message body: {raw_body[:100]}...")
                            sqs_handler.delete_message(receipt_handle)
                            continue
                        
                        if 'Message' in body:
                            # Safely parse the SNS message
                            raw_message = body.get('Message', '{}')
                            if not raw_message or not isinstance(raw_message, str):
                                app.logger.warning("Invalid or empty SNS message, skipping")
                                sqs_handler.delete_message(receipt_handle)
                                continue
                                
                            try:
                                sns_message = json.loads(raw_message)
                            except json.JSONDecodeError as json_err:
                                app.logger.warning(f"Invalid JSON in SNS message: {str(json_err)}")
                                app.logger.debug(f"Raw SNS message: {raw_message[:100]}...")
                                sqs_handler.delete_message(receipt_handle)
                                continue
                            notification_type = sns_message.get('notificationType') or sns_message.get('eventType')
                            
                            # Process the notification based on type
                            # Instead of directly importing handlers, we'll use our SNS notification endpoint
                            # which has access to the handler functions
                            try:
                                # Create a direct notification to the SNS endpoint
                                # This simulates SNS sending the notification to our webhook
                                from flask import url_for
                                import requests
                                
                                # Prepare the message for the endpoint
                                message_body = json.dumps({
                                    'Type': 'Notification',
                                    'Message': json.dumps(sns_message)
                                })
                                
                                # Get the server base URL from the app config or use localhost
                                # In development, use localhost
                                server_url = 'http://localhost:5000'
                                if app.config.get('SERVER_NAME'):
                                    protocol = 'https' if app.config.get('PREFERRED_URL_SCHEME') == 'https' else 'http'
                                    server_url = f"{protocol}://{app.config.get('SERVER_NAME')}"
                                
                                # Send to the webhook endpoint
                                endpoint_url = f"{server_url}/api/sns/ses-notification"
                                app.logger.info(f"Forwarding {notification_type} notification to endpoint: {endpoint_url}")
                                
                                # Use the Flask test client instead of making a real HTTP request
                                with app.test_client() as client:
                                    response = client.post(
                                        '/api/sns/ses-notification',
                                        data=message_body,
                                        content_type='application/json'
                                    )
                                    app.logger.info(f"Notification forwarding response: {response.status_code}")
                                    if response.status_code == 200:
                                        app.logger.info(f"Successfully processed {notification_type} notification")
                                    else:
                                        app.logger.error(f"Error processing {notification_type} notification: {response.data}")
                                
                            except Exception as process_err:
                                app.logger.error(f"Error processing notification: {str(process_err)}")
                                app.logger.error("Falling back to direct SQS message processing")
                            else:
                                app.logger.warning(f"Unknown notification type: {notification_type}")
                    
                        # Delete the message after successful processing
                        sqs_handler.delete_message(receipt_handle)
                        processed += 1
                        
                        # Add a small delay between messages to prevent overloading the server
                        time.sleep(0.5)
                        
                    except Exception as e:
                        app.logger.error(f"Error processing SQS message: {str(e)}")
        
                app.logger.info(f"Successfully processed {processed} SQS messages")
            except Exception as e:
                app.logger.error(f"Error processing SQS queue: {str(e)}")
    except Exception as e:
        logger.error(f"Error in SQS queue processing job: {str(e)}")
