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
    
    This function uses Flask's current_app pattern to avoid APScheduler serialization issues
    that occur when passing Flask app objects to job functions.
    """
    # Import Flask dependencies inside the function to avoid circular imports
    from flask import current_app
    
    try:
        # Process up to 10 messages per minute
        sqs_handler = current_app.get_sqs_handler()
        messages = sqs_handler.receive_messages(max_messages=10)
        
        if not messages:
            return
            
        current_app.logger.info(f"Processing {len(messages)} SQS messages from scheduled job")
        processed = 0
        
        for message in messages:
            try:
                # Extract and process the SNS message
                receipt_handle = message['ReceiptHandle']
                body = json.loads(message['Body'])
                
                if 'Message' in body:
                    sns_message = json.loads(body['Message'])
                    notification_type = sns_message.get('notificationType') or sns_message.get('eventType')
                    
                    # Use a safer approach that avoids circular imports
                    # Import notification handlers directly within this block scope
                    # This prevents circular import issues while still allowing access to handler functions
                    
                    # Get the global notification handlers
                    import sys
                    app_module = sys.modules.get('app')
                    
                    if app_module:
                        # Access handlers from the already imported app module
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
                        # Fallback if app module hasn't been imported yet
                        current_app.logger.error(f"Could not access notification handlers for {notification_type}")
                    
                    # Process logic already handled in the section above
                        
                # Delete the message after successful processing
                sqs_handler.delete_message(receipt_handle)
                processed += 1
                
                # Add a small delay between messages to prevent overloading the server
                time.sleep(0.5)
                
            except Exception as e:
                current_app.logger.error(f"Error processing SQS message: {str(e)}")
        
        current_app.logger.info(f"Successfully processed {processed} SQS messages")
        
    except Exception as e:
        logger.error(f"Error in SQS queue processing job: {str(e)}")
