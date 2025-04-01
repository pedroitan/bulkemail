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
import traceback
import psutil
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

def log_system_stats():
    """Log system resource usage for debugging"""
    try:
        process = psutil.Process()
        mem_info = process.memory_info()
        logger.info(f"SYSTEM STATS: Memory: {mem_info.rss / 1024 / 1024:.2f}MB, "
                   f"CPU: {psutil.cpu_percent()}%, "
                   f"Connections: {len(process.connections())}, "
                   f"Threads: {process.num_threads()}, "
                   f"Open files: {len(process.open_files())}")
    except Exception as e:
        logger.error(f"Error logging system stats: {str(e)}")

def main():
    # SQS processing is now permanently disabled to prevent notification flooding
    logger.warning("⚠️ SQS processing has been permanently disabled.")
    logger.warning("Email sending will still work, but delivery tracking is disabled.")
    logger.warning("This helps prevent application crashes after sending large numbers of emails.")
    return
        
    # Log initial system state
    log_system_stats()
        
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
    crash_count = 0
    max_crash_count = 5  # Prevent endless crash-restart cycles
    processing_cycle_count = 0
    
    try:
        while True:
            try:
                processing_cycle_count += 1
                
                # Log system stats every 10 cycles to track resource usage
                if processing_cycle_count % 10 == 0:
                    log_system_stats()
                    
                logger.info(f"Checking SQS queue for notifications (cycle {processing_cycle_count})...")
                messages_processed = process_sqs_queue_job()
                
                # Track SQS message processing in our stats
                if messages_processed > 0:
                    try:
                        # Log detailed message activity for debugging
                        logger.info(f"Processed {messages_processed} SQS messages - tracking usage")
                        
                        # Increment SQS message counter
                        for _ in range(messages_processed):
                            AWSUsageStats.increment_sqs_message_processed()
                            
                        # Get updated usage stats
                        usage = AWSUsageStats.get_monthly_usage()
                        logger.info(f"AWS Free Tier Usage: {usage['email_total']}/3000 emails ({usage['email_percent']}%), "
                                   f"{usage['sns_total']}/100000 SNS notifications ({usage['sns_percent']}%)")
                        
                        # If we've processed a high number of notifications, log system state
                        if messages_processed > 50:
                            logger.warning(f"High message load detected: {messages_processed} messages in one batch")
                            log_system_stats()
                            
                    except Exception as e:
                        logger.error(f"Error updating AWS usage stats: {str(e)}")
                        logger.error(traceback.format_exc())
                
                # Reset crash counter after successful processing
                crash_count = 0
                
                # Sleep for 15 seconds between processing batches
                # This prevents overwhelming the server while still providing timely updates
                logger.info("Waiting 15 seconds before next batch...")
                time.sleep(15)
                
            except Exception as e:
                crash_count += 1
                logger.error(f"Error processing SQS messages (crash #{crash_count}): {str(e)}")
                logger.error(traceback.format_exc())
                log_system_stats()
                
                # If we're crashing repeatedly, increase wait time exponentially
                wait_time = min(30 * (2 ** (crash_count - 1)), 300)  # Max 5 minutes
                logger.info(f"Waiting {wait_time} seconds before retrying...")
                time.sleep(wait_time)
                
                # If too many crashes, break loop and restart cleanly
                if crash_count >= max_crash_count:
                    logger.critical(f"Too many consecutive crashes ({crash_count}). Exiting to prevent instability.")
                    return
                
    except KeyboardInterrupt:
        logger.info("SQS processor stopped by user")
        
if __name__ == "__main__":
    main()
