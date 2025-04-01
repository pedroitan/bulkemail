"""
Test Email Delivery Status UI Updates

This script sends a test email and monitors for delivery status updates in the UI.
"""

import os
import sys
import time
import json
import requests
import logging
from datetime import datetime
from flask import Flask
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('DeliveryTester')

# Load environment variables
load_dotenv()

# Initialize minimal Flask app for database access
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///campaigns.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

def monitor_aws_usage():
    """Monitor AWS usage stats updates in the dashboard"""
    from aws_usage_model import AWSUsageStats
    from models import db
    
    # Initialize database
    db.init_app(app)
    
    with app.app_context():
        logger.info("Starting AWS usage monitoring test...")
        
        # Get initial AWS usage stats
        initial_stats = AWSUsageStats.get_or_create_today()
        logger.info(f"Initial AWS usage stats:")
        logger.info(f"  - Emails sent: {initial_stats.emails_sent_count}")
        logger.info(f"  - Emails delivered: {initial_stats.emails_delivered_count}")
        logger.info(f"  - SNS notifications: {initial_stats.sns_notifications_count}")
        logger.info(f"  - SQS messages: {initial_stats.sqs_messages_processed_count}")
        
        # Fetch API data
        try:
            logger.info("Checking AWS usage dashboard API...")
            response = requests.get("http://localhost:5000/api/aws-usage")
            api_data = response.json()
            
            logger.info("Current dashboard data:")
            logger.info(f"  - Emails sent: {api_data['today']['emails_sent']}")
            logger.info(f"  - Emails delivered: {api_data['today']['emails_delivered']}")
            logger.info(f"  - SNS notifications: {api_data['today']['sns_notifications']}")
            logger.info(f"  - SQS messages: {api_data['today']['sqs_messages']}")
            
            # Verify if dashboard matches database
            if (api_data['today']['emails_sent'] == initial_stats.emails_sent_count and
                api_data['today']['sns_notifications'] == initial_stats.sns_notifications_count):
                logger.info("✅ Success! Dashboard data matches database records.")
            else:
                logger.error("❌ Error: Dashboard data doesn't match database records.")
                logger.error(f"Database: {initial_stats.emails_sent_count} emails sent, {initial_stats.sns_notifications_count} SNS notifications")
                logger.error(f"Dashboard: {api_data['today']['emails_sent']} emails sent, {api_data['today']['sns_notifications']} SNS notifications")
        except Exception as e:
            logger.error(f"Error fetching API data: {str(e)}")
            
        # Test API endpoint with CloudWatch parameter
        try:
            logger.info("Testing CloudWatch refresh functionality...")
            response = requests.get("http://localhost:5000/api/aws-usage?use_cloudwatch=true")
            cloudwatch_data = response.json()
            logger.info(f"CloudWatch response source: {cloudwatch_data.get('source', 'unknown')}")
        except Exception as e:
            logger.error(f"Error testing CloudWatch refresh: {str(e)}")
        
        # Manually increment AWS usage counters to simulate activity
        logger.info("Simulating activity by incrementing usage counters...")
        
        # Increment email sent counter
        AWSUsageStats.increment_email_sent()
        
        # Increment email delivered counter
        initial_stats.emails_delivered_count += 1
        db.session.commit()
        
        # Increment SNS notification counter
        AWSUsageStats.increment_sns_notification()
        
        # Increment SQS message counter
        AWSUsageStats.increment_sqs_message_processed()
        
        # Wait for token bucket rate limiter to process
        time.sleep(2)
        
        # Fetch data again to see if updates are reflected
        try:
            logger.info("Checking if updates are reflected in the dashboard...")
            response = requests.get("http://localhost:5000/api/aws-usage")
            updated_data = response.json()
            
            logger.info("Updated dashboard data:")
            logger.info(f"  - Emails sent: {updated_data['today']['emails_sent']}")
            logger.info(f"  - Emails delivered: {updated_data['today']['emails_delivered']}")
            logger.info(f"  - SNS notifications: {updated_data['today']['sns_notifications']}")
            logger.info(f"  - SQS messages: {updated_data['today']['sqs_messages']}")
            
            # Verify updates were successful
            if (updated_data['today']['emails_sent'] > api_data['today']['emails_sent'] and
                updated_data['today']['sns_notifications'] > api_data['today']['sns_notifications']):
                logger.info("✅ Success! Updates were reflected in the dashboard.")
            else:
                logger.warning("⚠️ Warning: Updates may not be properly reflected in the dashboard.")
                
            # Test the CloudWatch refresh button functionality
            logger.info("Testing CloudWatch refresh button...")
            response = requests.get("http://localhost:5000/api/aws-usage?use_cloudwatch=true")
            cloudwatch_refresh_data = response.json()
            logger.info(f"CloudWatch refresh response source: {cloudwatch_refresh_data.get('source', 'unknown')}")
            
        except Exception as e:
            logger.error(f"Error checking for updates: {str(e)}")
        
        logger.info("Test completed successfully")

if __name__ == "__main__":
    logger.info("Starting AWS usage monitoring test")
    monitor_aws_usage()
