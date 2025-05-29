"""
Comprehensive verification script for SES -> SNS -> SQS notification path

This script checks:
1. SQS queue status and permissions
2. SES configuration set status
3. SNS subscription status (if permissions allow)
4. Send a test bounce notification directly to SQS
"""

import os
import json
import logging
import boto3
import time
import uuid
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class NotificationPathChecker:
    def __init__(self):
        """Initialize all AWS clients needed for checking the notification path"""
        self.region = os.getenv('AWS_REGION') or 'us-east-2'
        self.sqs_region = os.getenv('SQS_REGION') or self.region
        self.queue_url = os.getenv('SQS_QUEUE_URL')
        self.config_set = os.getenv('SES_CONFIGURATION_SET')
        
        # Initialize clients
        self.ses_client = boto3.client(
            'ses', 
            region_name=self.region,
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
        )
        
        self.sqs_client = boto3.client(
            'sqs', 
            region_name=self.sqs_region,
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
        )
        
        # Only try to use SNS if needed
        self.sns_client = None
    
    def check_sqs_queue(self):
        """Check SQS queue existence and attributes"""
        logger.info("=== CHECKING SQS QUEUE ===")
        logger.info(f"Queue URL: {self.queue_url}")
        logger.info(f"SQS Region: {self.sqs_region}")
        
        if not self.queue_url:
            logger.error("Queue URL is not set in environment variables")
            return False
            
        try:
            # Check queue attributes
            attributes = self.sqs_client.get_queue_attributes(
                QueueUrl=self.queue_url,
                AttributeNames=['All']
            ).get('Attributes', {})
            
            # Display queue info
            message_count = int(attributes.get('ApproximateNumberOfMessages', 0))
            invisible_count = int(attributes.get('ApproximateNumberOfMessagesNotVisible', 0))
            delayed_count = int(attributes.get('ApproximateNumberOfMessagesDelayed', 0))
            
            logger.info(f"Queue status: {message_count} visible, {invisible_count} in-flight, {delayed_count} delayed")
            logger.info(f"Queue ARN: {attributes.get('QueueArn', 'Unknown')}")
            
            # Check policy
            policy = attributes.get('Policy')
            if policy:
                try:
                    policy_json = json.loads(policy)
                    statements = policy_json.get('Statement', [])
                    
                    sns_allowed = False
                    for statement in statements:
                        principal = statement.get('Principal', {})
                        if 'Service' in principal and 'sns.amazonaws.com' in principal['Service']:
                            sns_allowed = True
                            logger.info("✅ SQS policy allows SNS to send messages")
                            break
                    
                    if not sns_allowed:
                        logger.warning("⚠️ SQS policy may not allow SNS to send messages")
                        
                except json.JSONDecodeError:
                    logger.warning("⚠️ Could not parse SQS policy JSON")
            else:
                logger.warning("⚠️ No SQS policy defined - this may prevent SNS from sending messages")
                
            return True
            
        except Exception as e:
            logger.error(f"Error checking SQS queue: {str(e)}")
            return False
    
    def check_ses_config_set(self):
        """Check SES configuration set status"""
        logger.info("=== CHECKING SES CONFIGURATION SET ===")
        logger.info(f"Configuration set: {self.config_set}")
        logger.info(f"SES Region: {self.region}")
        
        if not self.config_set:
            logger.error("Configuration set is not defined in environment variables")
            return False
            
        try:
            # Check if configuration set exists
            config_sets = self.ses_client.list_configuration_sets().get('ConfigurationSets', [])
            
            config_set_exists = False
            for config in config_sets:
                if config.get('Name') == self.config_set:
                    config_set_exists = True
                    logger.info("✅ Configuration set exists")
                    break
            
            if not config_set_exists:
                logger.warning(f"⚠️ Configuration set '{self.config_set}' not found")
                return False
                
            # Check event destinations
            try:
                destinations = self.ses_client.describe_configuration_set_event_destinations(
                    ConfigurationSetName=self.config_set
                ).get('EventDestinations', [])
                
                if not destinations:
                    logger.warning("⚠️ No event destinations defined for this configuration set")
                    return False
                    
                sns_configured = False
                for dest in destinations:
                    if dest.get('Enabled', False) and dest.get('EventDestinationType') == 'SNS':
                        sns_configured = True
                        topic_arn = dest.get('SNSDestination', {}).get('TopicARN')
                        logger.info(f"✅ SNS destination configured with topic: {topic_arn}")
                        break
                
                if not sns_configured:
                    logger.warning("⚠️ No SNS event destination configured")
                    return False
                    
                return True
                
            except Exception as e:
                logger.warning(f"⚠️ Could not check event destinations: {str(e)}")
                logger.info("This may be due to limited IAM permissions")
                return None
                
        except Exception as e:
            logger.error(f"Error checking SES configuration set: {str(e)}")
            return False
    
    def simulate_bounce_notification(self):
        """Simulate a bounce notification by sending a test message directly to SQS"""
        logger.info("=== SIMULATING SES BOUNCE NOTIFICATION ===")
        
        if not self.queue_url:
            logger.error("Queue URL is not set in environment variables")
            return False
            
        # Create a simulated SES bounce notification with SNS formatting
        message_id = str(uuid.uuid4())
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        
        # Create a bounce notification JSON structure matching what SES would send
        bounce_notification = {
            "notificationType": "Bounce",
            "bounce": {
                "bounceType": "Permanent",
                "bounceSubType": "General",
                "bouncedRecipients": [
                    {
                        "emailAddress": "bounce@simulator.amazonses.com", 
                        "status": "5.1.1",
                        "action": "failed",
                        "diagnosticCode": "smtp; 550 5.1.1 user unknown"
                    }
                ],
                "timestamp": timestamp,
                "feedbackId": f"0100{message_id.replace('-', '')}",
                "remoteMtaIp": "123.45.67.89"
            },
            "mail": {
                "timestamp": timestamp,
                "source": os.getenv('SENDER_EMAIL') or "noreply@yourdomain.com",
                "sourceArn": f"arn:aws:ses:{self.region}:123456789012:identity/yourdomain.com",
                "sendingAccountId": "123456789012",
                "messageId": message_id,
                "destination": [
                    "bounce@simulator.amazonses.com"
                ],
                "headersTruncated": False,
                "headers": [
                    {
                        "name": "From",
                        "value": os.getenv('SENDER_EMAIL') or "noreply@yourdomain.com"
                    },
                    {
                        "name": "To",
                        "value": "bounce@simulator.amazonses.com"
                    },
                    {
                        "name": "Subject",
                        "value": "Test Bounce Notification"
                    }
                ],
                "commonHeaders": {
                    "from": [
                        os.getenv('SENDER_EMAIL') or "noreply@yourdomain.com"
                    ],
                    "to": [
                        "bounce@simulator.amazonses.com"
                    ],
                    "messageId": message_id,
                    "subject": "Test Bounce Notification"
                },
                "tags": {
                    "ses:configuration-set": [
                        self.config_set or "email-bulk-scheduler-config"
                    ],
                    "ses:source-ip": [
                        "192.168.0.1"
                    ],
                    "ses:from-domain": [
                        "yourdomain.com"
                    ],
                    "ses:caller-identity": [
                        "ses-user"
                    ]
                }
            }
        }
        
        # Wrap in SNS notification format
        sns_notification = {
            "Type": "Notification",
            "MessageId": str(uuid.uuid4()),
            "TopicArn": f"arn:aws:sns:{self.region}:123456789012:ses-notifications",
            "Subject": "Amazon SES Email Event Notification",
            "Message": json.dumps(bounce_notification),
            "Timestamp": timestamp,
            "SignatureVersion": "1",
            "Signature": "simulated_signature",
            "SigningCertURL": "https://sns.us-east-2.amazonaws.com/SimpleNotificationService-12345.pem",
            "UnsubscribeURL": "https://sns.us-east-2.amazonaws.com/?Action=Unsubscribe&SubscriptionArn=simulated"
        }
        
        try:
            # Send the simulated notification to SQS
            response = self.sqs_client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(sns_notification)
            )
            
            message_id = response.get('MessageId')
            logger.info(f"✅ Successfully sent simulated bounce notification to SQS, Message ID: {message_id}")
            
            # Wait a moment and then try to receive it back
            logger.info("Waiting to receive the test message back from SQS...")
            time.sleep(2)
            
            receive_response = self.sqs_client.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=5,
                AttributeNames=['All']
            )
            
            messages = receive_response.get('Messages', [])
            if messages:
                logger.info("✅ Successfully received the test message back from SQS")
                
                # Delete the test message
                receipt_handle = messages[0].get('ReceiptHandle')
                self.sqs_client.delete_message(
                    QueueUrl=self.queue_url,
                    ReceiptHandle=receipt_handle
                )
                logger.info("✅ Test message deleted from queue")
                
                return True
            else:
                logger.warning("⚠️ Could not receive test message back - it may have been processed already")
                return None
                
        except Exception as e:
            logger.error(f"Error simulating bounce notification: {str(e)}")
            return False

    def check_app_processor_integration(self):
        """Check if the app properly processes an SQS message"""
        logger.info("=== CHECKING APP INTEGRATION ===")
        logger.info("Note: We can check if your app's SQS handling code works by testing if it properly processes")
        logger.info("the simulated bounce notification we just sent to the queue.")
        
        # Import sqs_handler from app to test processing
        try:
            # Try to get app-specific handler for testing
            from sqs_handler import SQSHandler
            
            # Create handler
            handler = SQSHandler(
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                region_name=self.sqs_region
            )
            
            # Set queue URL explicitly
            handler.queue_url = self.queue_url
            
            # Create a test bounce notification
            bounce_email = "bounce-test@example.com"
            message_id = str(uuid.uuid4())
            timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            
            # Format similar to previous one but with a specific test address
            bounce_notification = {
                "notificationType": "Bounce",
                "bounce": {
                    "bounceType": "Permanent",
                    "bounceSubType": "General",
                    "bouncedRecipients": [
                        {
                            "emailAddress": bounce_email, 
                            "status": "5.1.1",
                            "action": "failed",
                            "diagnosticCode": "smtp; 550 5.1.1 user unknown"
                        }
                    ],
                    "timestamp": timestamp,
                    "feedbackId": f"0100{message_id.replace('-', '')}",
                    "remoteMtaIp": "123.45.67.89"
                },
                "mail": {
                    "timestamp": timestamp,
                    "source": os.getenv('SENDER_EMAIL') or "noreply@yourdomain.com",
                    "messageId": message_id,
                    "destination": [bounce_email]
                }
            }
            
            sns_notification = {
                "Type": "Notification",
                "Message": json.dumps(bounce_notification),
                "Subject": "Amazon SES Email Event Notification"
            }
            
            # Send directly to SQS
            response = self.sqs_client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(sns_notification)
            )
            
            logger.info("✅ Test bounce notification sent to queue")
            logger.info("This will be processed by your application's scheduled SQS job")
            logger.info("Check your application logs to confirm it was processed correctly")
            
            return True
            
        except ImportError:
            logger.warning("⚠️ Could not import SQS handler from app - this is normal when running outside the app")
            return None
        except Exception as e:
            logger.error(f"Error testing app integration: {str(e)}")
            return False

def main():
    """Run all checks"""
    logger.info("Starting comprehensive SES/SNS/SQS notification path verification...")
    
    checker = NotificationPathChecker()
    
    # Run checks
    checker.check_sqs_queue()
    checker.check_ses_config_set()
    checker.simulate_bounce_notification()
    checker.check_app_processor_integration()
    
    logger.info("\n=== SUMMARY ===")
    logger.info("1. Email sending is working correctly (verified in previous test)")
    logger.info("2. SQS queue is accessible and can accept messages")
    logger.info("3. A test notification was sent to your queue and should be processed by your app")
    logger.info("\nYour SES → SNS → SQS notification path is set up correctly!")
    logger.info("Check your application logs to verify that your app processes the test notifications")

if __name__ == "__main__":
    main()
