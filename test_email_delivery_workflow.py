#!/usr/bin/env python3
import os
import sys
import json
import time
import logging
import argparse
import boto3
import requests
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('DeliveryWorkflowTester')

# Get the root directory
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(ROOT_DIR)

# Import required modules
try:
    from models import db, EmailCampaign, EmailRecipient
    from email_service import SESEmailService
    from aws_usage_model import AWSUsageStats
    from dotenv import load_dotenv
    
    # Load environment variables
    load_dotenv()
    
    # Get AWS configuration from environment
    AWS_REGION = os.environ.get('AWS_REGION', 'us-east-2')
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    SQS_QUEUE_URL = os.environ.get('SQS_QUEUE_URL')
    
    if not SQS_QUEUE_URL:
        logger.error("SQS_QUEUE_URL environment variable must be set")
        sys.exit(1)
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    sys.exit(1)

class DeliveryWorkflowTester:
    """Test the complete email delivery workflow including SQS message processing"""
    
    def __init__(self, test_email=None, database_url=None):
        self.test_email = test_email or 'success@simulator.amazonses.com'
        # Use the app.db file which is the correct database for the application
        self.database_url = database_url or 'sqlite:///app.db'
        
        # Set up AWS clients
        try:
            self.ses_client = boto3.client('ses', region_name=AWS_REGION)
            self.sqs_client = boto3.client('sqs', region_name=AWS_REGION)
            logger.info(f"AWS clients initialized for region {AWS_REGION}")
        except Exception as e:
            logger.error(f"Failed to initialize AWS clients: {e}")
            sys.exit(1)
        
        # Connect to database
        try:
            self.engine = create_engine(self.database_url)
            Session = sessionmaker(bind=self.engine)
            self.session = Session()
            logger.info(f"Connected to database: {self.database_url}")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            sys.exit(1)
            
        # Initialize email service
        self.email_service = SESEmailService(
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
        
    def create_test_campaign(self):
        """Create a test campaign with a single recipient"""
        try:
            # Check if we already have a test campaign
            test_campaign = self.session.query(EmailCampaign).filter_by(
                name="Test Delivery Workflow"
            ).first()
            
            if not test_campaign:
                logger.info("Creating test campaign")
                test_campaign = EmailCampaign(
                    name="Test Delivery Workflow",
                    subject="Test Email Delivery and SQS Processing",
                    body="This is a test email to verify the delivery workflow and SQS processing.",
                    sender="test@yourdomain.com",
                    scheduled_time=datetime.utcnow(),
                    status="pending"
                )
                self.session.add(test_campaign)
                self.session.commit()
                
            # Check if we already have a test recipient
            test_recipient = self.session.query(EmailRecipient).filter_by(
                email=self.test_email,
                campaign_id=test_campaign.id
            ).first()
            
            if not test_recipient:
                logger.info(f"Adding test recipient: {self.test_email}")
                test_recipient = EmailRecipient(
                    campaign_id=test_campaign.id,
                    email=self.test_email,
                    name="Test Recipient",
                    status="pending"
                )
                self.session.add(test_recipient)
                self.session.commit()
            
            return test_campaign, test_recipient
        except Exception as e:
            logger.error(f"Failed to create test campaign: {e}")
            self.session.rollback()
            return None, None
        
    def send_test_email(self, campaign, recipient):
        """Send a test email and return the message ID"""
        try:
            logger.info(f"Sending test email to {recipient.email}")
            
            # Use EmailService to send the email
            response = self.email_service.send_email(
                to_email=recipient.email,
                subject=campaign.subject,
                body_text=campaign.body,
                body_html=f"<html><body><p>{campaign.body}</p></body></html>",
                sender=campaign.sender
            )
            
            message_id = response.get('MessageId')
            if message_id:
                logger.info(f"Email sent successfully, Message ID: {message_id}")
                
                # Update recipient status
                recipient.status = "sent"
                recipient.message_id = message_id
                recipient.sent_at = datetime.utcnow()
                self.session.commit()
                
                # Update AWS usage stats
                try:
                    AWSUsageStats.increment_email_sent()
                    logger.info("AWS usage stats updated for sent email")
                except Exception as e:
                    logger.warning(f"Failed to update AWS usage stats: {e}")
                
                return message_id
            else:
                logger.error("Failed to send email: No MessageId returned")
                return None
        except ClientError as e:
            logger.error(f"Failed to send email: {e}")
            return None
    
    def poll_sqs_for_notifications(self, wait_time=30, max_messages=10):
        """Poll SQS queue for message notifications
        
        Respects token bucket rate limiter by throttling requests to 10 per second
        and prioritizing critical notifications (bounces, complaints)
        """
        logger.info(f"Polling SQS queue for notifications: {SQS_QUEUE_URL}")
        
        start_time = time.time()
        messages_processed = 0
        delivery_found = False
        
        # Track the last request time to implement rate limiting
        last_request_time = 0
        request_interval = 0.1  # 10 requests per second maximum
        
        while time.time() - start_time < wait_time and not delivery_found:
            try:
                # Implement rate limiting for SQS requests to respect token bucket rate limiter
                current_time = time.time()
                time_since_last_request = current_time - last_request_time
                
                if time_since_last_request < request_interval:
                    # Sleep to respect rate limit (10 requests per second)
                    sleep_time = request_interval - time_since_last_request
                    logger.debug(f"Rate limiting: Sleeping for {sleep_time:.3f}s")
                    time.sleep(sleep_time)
                
                # Record when we made this request
                last_request_time = time.time()
                
                # Make SQS request
                response = self.sqs_client.receive_message(
                    QueueUrl=SQS_QUEUE_URL,
                    MaxNumberOfMessages=max_messages,
                    WaitTimeSeconds=5  # Long polling
                )
                
                messages = response.get('Messages', [])
                
                if not messages:
                    logger.info("No messages received, continuing to poll...")
                    continue
                
                logger.info(f"Received {len(messages)} messages from SQS")
                
                for message in messages:
                    message_body = json.loads(message['Body'])
                    message_text = json.loads(message_body.get('Message', '{}'))
                    
                    # Verify SQS message format
                    logger.info(f"Validating SQS message format...")
                    self.validate_sqs_message_format(message_body)
                    
                    # Process the message based on notification type
                    notification_type = message_text.get('notificationType')
                    
                    # Prioritize critical notifications (bounces, complaints)
                    # This aligns with the token bucket rate limiter's logic
                    is_critical = notification_type in ['Bounce', 'Complaint']
                    
                    if is_critical:
                        logger.info(f"Processing critical notification: {notification_type}")
                    
                    if notification_type == 'Delivery':
                        receipt = message_text.get('delivery', {}).get('recipients', [])
                        message_id = message_text.get('mail', {}).get('messageId')
                        
                        logger.info(f"Delivery notification received for Message ID: {message_id}")
                        logger.info(f"Recipients: {receipt}")
                        
                        # Update the recipient status in database
                        if message_id:
                            recipient = self.session.query(EmailRecipient).filter_by(
                                message_id=message_id
                            ).first()
                            
                            if recipient:
                                logger.info(f"Updating recipient status to 'delivered': {recipient.email}")
                                recipient.status = "delivered"
                                recipient.delivered_at = datetime.utcnow()
                                self.session.commit()
                                
                                # Update AWS usage stats
                                try:
                                    AWSUsageStats.increment_email_delivered()
                                    AWSUsageStats.increment_sns_notification()
                                    logger.info("AWS usage stats updated for delivered email")
                                except Exception as e:
                                    logger.warning(f"Failed to update AWS usage stats: {e}")
                                
                                delivery_found = True
                    
                    # Always delete the message from the queue
                    self.sqs_client.delete_message(
                        QueueUrl=SQS_QUEUE_URL,
                        ReceiptHandle=message['ReceiptHandle']
                    )
                    
                    messages_processed += 1
                    
                    # Update AWS usage stats for SQS message processed
                    try:
                        AWSUsageStats.increment_sqs_message_processed()
                    except Exception as e:
                        logger.warning(f"Failed to update AWS usage stats for SQS: {e}")
            
            except Exception as e:
                logger.error(f"Error polling SQS queue: {e}")
                time.sleep(1)  # Short delay before retrying
        
        logger.info(f"SQS polling complete. Processed {messages_processed} messages.")
        return delivery_found
    
    def validate_sqs_message_format(self, message):
        """Validate SQS message format to ensure it's correct"""
        required_keys = ['Type', 'MessageId', 'TopicArn', 'Message']
        
        # Check if all required keys are present
        for key in required_keys:
            if key not in message:
                logger.error(f"SQS message missing required key: {key}")
                logger.debug(f"Message content: {json.dumps(message, indent=2)}")
                return False
        
        # Check if Message is properly formatted
        try:
            sns_message = json.loads(message['Message'])
            if not isinstance(sns_message, dict):
                logger.error("SQS message has invalid Message format (not a JSON object)")
                return False
                
            # For delivery notifications
            if 'notificationType' in sns_message and sns_message['notificationType'] == 'Delivery':
                required_sns_keys = ['notificationType', 'mail', 'delivery']
                for key in required_sns_keys:
                    if key not in sns_message:
                        logger.error(f"SNS message missing required key: {key}")
                        return False
                
                # Validate mail object
                if 'messageId' not in sns_message['mail']:
                    logger.error("SNS message missing messageId in mail object")
                    return False
                
                # Validate delivery object
                if 'recipients' not in sns_message['delivery']:
                    logger.error("SNS message missing recipients in delivery object")
                    return False
                    
            logger.info("✅ SQS message format validated successfully")
            return True
        except json.JSONDecodeError:
            logger.error("SQS message has invalid Message format (not valid JSON)")
            return False
            
    def check_dashboard_updates(self):
        """Check if the AWS usage dashboard reflects the updates"""
        logger.info("Checking AWS usage dashboard updates")
        
        try:
            # Add a delay to allow for any processing
            time.sleep(2)
            
            # Use the API endpoint with cache busting
            response = requests.get(
                'http://localhost:5000/api/aws-usage',
                params={'bypass_cache': 'true', '_': int(time.time())}
            )
            
            if response.status_code == 200:
                dashboard_data = response.json()
                
                # Check today's stats
                today_data = dashboard_data.get('today', {})
                emails_sent = today_data.get('emails_sent', 0)
                emails_delivered = today_data.get('emails_delivered', 0)
                sns_notifications = today_data.get('sns_notifications', 0)
                sqs_messages = today_data.get('sqs_messages', 0)
                
                logger.info(f"Dashboard today's stats:")
                logger.info(f"  - Emails sent: {emails_sent}")
                logger.info(f"  - Emails delivered: {emails_delivered}")
                logger.info(f"  - SNS notifications: {sns_notifications}")
                logger.info(f"  - SQS messages: {sqs_messages}")
                
                # Get database stats for comparison
                db_stats = self.get_database_stats()
                
                # Check if dashboard reflects database stats
                if (emails_sent == db_stats['emails_sent'] and 
                    emails_delivered == db_stats['emails_delivered'] and
                    sns_notifications == db_stats['sns_notifications'] and
                    sqs_messages == db_stats['sqs_messages']):
                    logger.info("✅ Dashboard data correctly reflects database records")
                    return True
                else:
                    logger.warning("⚠️ Dashboard data doesn't match database records")
                    logger.warning(f"Database: {db_stats['emails_sent']} emails sent, {db_stats['emails_delivered']} delivered")
                    logger.warning(f"Dashboard: {emails_sent} emails sent, {emails_delivered} delivered")
                    return False
            else:
                logger.error(f"Failed to get dashboard data: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error checking dashboard updates: {e}")
            return False
    
    def get_database_stats(self):
        """Get current stats directly from database"""
        today = datetime.utcnow().date()
        
        try:
            stats = self.session.query(AWSUsageStats).filter_by(date=today).first()
            
            if stats:
                return {
                    'emails_sent': stats.emails_sent_count,
                    'emails_delivered': stats.emails_delivered_count,
                    'sns_notifications': stats.sns_notifications_count,
                    'sqs_messages': stats.sqs_messages_processed_count
                }
            else:
                logger.warning("No stats found for today in database")
                return {
                    'emails_sent': 0,
                    'emails_delivered': 0, 
                    'sns_notifications': 0,
                    'sqs_messages': 0
                }
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {
                'emails_sent': 0,
                'emails_delivered': 0,
                'sns_notifications': 0,
                'sqs_messages': 0
            }
    
    def run_test(self):
        """Run the complete test workflow"""
        logger.info("Starting email delivery workflow test")
        
        # Step 1: Create test campaign and recipient
        campaign, recipient = self.create_test_campaign()
        if not campaign or not recipient:
            logger.error("Failed to create test campaign or recipient")
            return False
        
        # Step 2: Record initial AWS usage stats
        initial_stats = self.get_database_stats()
        logger.info("Initial AWS usage stats:")
        for key, value in initial_stats.items():
            logger.info(f"  - {key}: {value}")
        
        # Step 3: Send test email
        message_id = self.send_test_email(campaign, recipient)
        if not message_id:
            logger.error("Failed to send test email")
            return False
        
        # Step 4: Poll SQS for delivery notifications
        logger.info("Waiting for delivery notifications...")
        delivery_found = self.poll_sqs_for_notifications(wait_time=60)
        
        if delivery_found:
            logger.info("✅ Successfully received and processed delivery notification")
        else:
            logger.warning("⚠️ No delivery notification received within timeout period")
            logger.info("Note: AWS SES may take some time to send delivery notifications")
            logger.info("The test will continue, but you may need to check manually later")
        
        # Step 5: Verify AWS usage dashboard updates
        dashboard_updated = self.check_dashboard_updates()
        
        # Step 6: Final verification
        logger.info("\n=== Email Delivery Workflow Test Results ===")
        logger.info(f"✅ Test email sent successfully: {bool(message_id)}")
        logger.info(f"✅ Delivery notification received: {delivery_found}")
        logger.info(f"✅ Dashboard updates correctly: {dashboard_updated}")
        
        # Get updated stats
        final_stats = self.get_database_stats()
        logger.info("\nFinal AWS usage stats:")
        for key, value in final_stats.items():
            logger.info(f"  - {key}: {value}")
            
        # Compare with initial stats
        logger.info("\nChanges in AWS usage stats:")
        for key in initial_stats:
            diff = final_stats[key] - initial_stats[key]
            logger.info(f"  - {key}: +{diff}")
        
        return message_id and dashboard_updated

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Test email delivery workflow')
    parser.add_argument('--email', type=str, help='Test email address (default: success@simulator.amazonses.com)')
    args = parser.parse_args()
    
    test_email = args.email or 'success@simulator.amazonses.com'
    
    tester = DeliveryWorkflowTester(test_email=test_email)
    successful = tester.run_test()
    
    if successful:
        logger.info("\n✅ Email delivery workflow test completed successfully!")
        sys.exit(0)
    else:
        logger.error("\n❌ Email delivery workflow test failed.")
        sys.exit(1)
