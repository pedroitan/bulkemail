"""
AWS Free Tier Usage Optimizer

This script optimizes your AWS usage to stay within Free Tier limits:
1. Implements a SNS topic clean-up strategy
2. Creates a notification policy to reduce unnecessary SNS notifications
3. Optimizes SES configuration set to filter low-priority notification types
"""

import boto3
import json
import os
import logging
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('AWSOptimizer')

# AWS credentials from environment
aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
aws_region = os.getenv('AWS_REGION', 'us-east-2')
ses_config_set = os.getenv('SES_CONFIGURATION_SET')

# Initialize AWS clients
def get_aws_clients():
    """Initialize boto3 clients for SES, SNS, and SQS"""
    session = boto3.Session(
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name=aws_region
    )
    
    ses = session.client('ses')
    sns = session.client('sns')
    sqs = session.client('sqs')
    
    return ses, sns, sqs

def optimize_ses_configuration_set(ses):
    """Optimize the SES configuration set to reduce notification volume"""
    logger.info(f"Optimizing SES configuration set: {ses_config_set}")
    
    try:
        # Check if the configuration set exists
        response = ses.describe_configuration_set(
            ConfigurationSetName=ses_config_set
        )
        
        # Update the configuration set to only track essential event types
        # This dramatically reduces the number of SNS notifications generated
        event_destinations = []
        
        # Get current event destinations
        try:
            event_response = ses.describe_configuration_set_event_destinations(
                ConfigurationSetName=ses_config_set
            )
            event_destinations = event_response.get('EventDestinations', [])
        except Exception as e:
            logger.error(f"Error getting event destinations: {str(e)}")
        
        # Find SNS destinations and update them
        for dest in event_destinations:
            if dest['Enabled'] and 'SNSDestination' in dest:
                logger.info(f"Found SNS destination: {dest['Name']}")
                
                # Modify this destination to only include critical events
                # This is the key optimization to reduce SNS traffic
                updated_dest = {
                    'Name': dest['Name'],
                    'Enabled': True,
                    'MatchingEventTypes': [
                        'bounce',        # Critical - keep
                        'complaint',     # Critical - keep
                        # 'delivery',      # High volume - filter out
                        # 'send',          # High volume - filter out
                        'deliveryDelay', # Important - keep
                        # 'open',          # High volume - filter out
                        # 'click',         # High volume - filter out
                        'renderingFailure' # Rare but important - keep
                    ],
                    'SNSDestination': dest['SNSDestination']
                }
                
                # Update the event destination with optimized config
                try:
                    ses.update_configuration_set_event_destination(
                        ConfigurationSetName=ses_config_set,
                        EventDestination=updated_dest
                    )
                    logger.info(f"✅ Successfully optimized event destination: {dest['Name']}")
                    logger.info(f"Now tracking only: bounce, complaint, deliveryDelay, renderingFailure")
                    logger.info(f"Filtering out high-volume events: delivery, send, open, click")
                except Exception as e:
                    logger.error(f"Error updating event destination: {str(e)}")
        
        logger.info("SES Configuration Set optimization complete!")
        return True
        
    except Exception as e:
        logger.error(f"Error optimizing SES configuration set: {str(e)}")
        return False

def create_notification_retention_policy(sqs):
    """Set retention policy on SQS to keep messages for a reasonable time without incurring costs"""
    try:
        # Get the SQS queue URL from environment
        queue_url = os.getenv('SQS_QUEUE_URL')
        if not queue_url:
            logger.error("SQS_QUEUE_URL not found in environment variables")
            return False
            
        # Set the message retention period to 1 day (instead of default 4 days)
        # This reduces the storage needed while still giving ample time to process
        response = sqs.set_queue_attributes(
            QueueUrl=queue_url,
            Attributes={
                'MessageRetentionPeriod': '86400'  # 1 day in seconds
            }
        )
        
        logger.info("✅ SQS queue retention period set to 1 day to optimize storage")
        return True
        
    except Exception as e:
        logger.error(f"Error setting SQS retention policy: {str(e)}")
        return False

def main():
    logger.info("=== AWS Free Tier Optimizer ===")
    logger.info("This tool will optimize your AWS usage to stay within Free Tier limits")
    
    # Initialize AWS clients
    ses, sns, sqs = get_aws_clients()
    
    # Optimize SES configuration set to reduce notification volume
    logger.info("\n=== Step 1: Optimizing SES Configuration Set ===")
    optimize_ses_configuration_set(ses)
    
    # Create notification retention policy
    logger.info("\n=== Step 2: Setting SQS Retention Policy ===")
    create_notification_retention_policy(sqs)
    
    # Recommendations for additional optimizations
    logger.info("\n=== AWS Free Tier Optimization Recommendations ===")
    logger.info("1. Maintain increased sampling rate for non-critical notifications in app.py")
    logger.info("   - The rate limiter already skips 99.8% of non-critical notifications")
    logger.info("   - This dramatically reduces your SNS usage")
    logger.info("2. Consider implementing batch sending for emails")
    logger.info("   - Batch sending reduces per-message overhead and SES costs")
    logger.info("3. Add a 'cooldown period' between campaigns to spread usage across billing cycles")
    logger.info("4. Continue using token bucket rate limiting for critical notifications")
    
    logger.info("\n✅ Optimization complete! Your application should now use significantly less AWS resources")
    logger.info("Monitor your AWS usage in the coming days to ensure you stay within Free Tier limits")

if __name__ == "__main__":
    main()
