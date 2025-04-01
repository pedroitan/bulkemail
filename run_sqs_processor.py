"""
SQS Notification Processor Runner

This script starts the SQS notification processor and keeps it running
to process delivery status updates from AWS SES. This is designed to
be compatible with your token bucket rate limiter implementation.

Now includes AWS usage tracking to help monitor free tier limits.
"""

import time
import logging
import os
import sys
from flask import Flask
from dotenv import load_dotenv

# Add parent directory to path so we can import our modules
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the AWS usage stats model
from aws_usage_model import AWSUsageStats

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SQSProcessor")

def main():
    # Check if SQS processing is disabled
    if os.environ.get('DISABLE_SQS_PROCESSING', 'false').lower() == 'true':
        logger.warning("⚠️ SQS processing has been disabled. Exiting.")
        logger.warning("Email sending will still work, but delivery tracking is disabled.")
        return
        
    # Print information about what this script does
    logger.info("=== Email Delivery Status Processor ===")
    logger.info("This script processes AWS SES delivery notifications from your SQS queue")
    logger.info("It will update the delivery status of your emails in the database")
    logger.info("Compatible with your token bucket rate limiter to prevent server overload")
    logger.info(f"Using SQS queue: {os.environ.get('SQS_QUEUE_URL')}")
    
    # Import the process_sqs_queue_job function from sqs_jobs.py
    from sqs_jobs import process_sqs_queue_job, create_app
    
    # Initialize Flask app context for database access
    app = create_app()
    app_context = app.app_context()
    app_context.push()
    
    # Initialize the AWS usage stats
    try:
        # Get current monthly usage
        usage = AWSUsageStats.get_monthly_usage()
        logger.info(f"Current AWS Free Tier Usage: {usage['email_total']}/3000 emails, {usage['sns_total']}/100000 SNS notifications")
        logger.info(f"SES usage: {usage['email_percent']}%, SNS usage: {usage['sns_percent']}%")
    except Exception as e:
        logger.error(f"Error initializing AWS usage stats: {str(e)}")
    
    # Run the processor in a loop
    logger.info("Starting SQS processor loop...")
    try:
        while True:
            try:
                logger.info("Checking SQS queue for notifications...")
                messages_processed = process_sqs_queue_job()
                
                # Track SQS message processing in our stats
                if messages_processed > 0:
                    try:
                        # Increment SQS message counter
                        for _ in range(messages_processed):
                            AWSUsageStats.increment_sqs_message_processed()
                            
                        # Get updated usage stats
                        usage = AWSUsageStats.get_monthly_usage()
                        logger.info(f"AWS Free Tier Usage: {usage['email_total']}/3000 emails ({usage['email_percent']}%), {usage['sns_total']}/100000 SNS notifications ({usage['sns_percent']}%)")
                    except Exception as e:
                        logger.error(f"Error updating AWS usage stats: {str(e)}")
                
                # Sleep for 15 seconds between processing batches
                # This prevents overwhelming the server while still providing timely updates
                logger.info("Waiting 15 seconds before next batch...")
                time.sleep(15)
                
            except Exception as e:
                logger.error(f"Error processing SQS messages: {str(e)}")
                # Wait a bit longer if there was an error
                logger.info("Waiting 30 seconds before retrying...")
                time.sleep(30)
                
    except KeyboardInterrupt:
        logger.info("SQS processor stopped by user")
        
if __name__ == "__main__":
    main()
