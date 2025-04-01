"""
SQS background job for handling AWS SNS notifications queued in SQS

This module provides a standalone function for processing SQS messages
containing SNS notifications. It is designed to be used with APScheduler
in a way that avoids serialization issues.
"""

import json
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
                messages = sqs_handler.receive_messages(max_messages=10)
                
                if not messages:
                    return
                    
                app.logger.info(f"Processing {len(messages)} SQS messages from scheduled job")
                processed = 0
        
                for message in messages:
                    try:
                        # Extract and process the SNS message
                        receipt_handle = message['ReceiptHandle']
                        
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
                            if notification_type == 'Bounce':
                                app_module.handle_bounce_notification(sns_message)
                            elif notification_type == 'Complaint':
                                app_module.handle_complaint_notification(sns_message)
                            elif notification_type == 'Delivery':
                                app_module.handle_delivery_notification(sns_message)
                            elif notification_type == 'DeliveryDelay':
                                app_module.handle_delivery_delay_notification(sns_message)
                            elif notification_type == 'Open':
                                app_module.handle_open_notification(sns_message)
                            elif notification_type == 'Click':
                                app_module.handle_click_notification(sns_message)
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
