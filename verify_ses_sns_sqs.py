import boto3
import json
import time
import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# AWS configuration
aws_region = os.getenv('AWS_REGION', 'us-east-2')
aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
sender_email = os.getenv('SENDER_EMAIL')
ses_config_set = os.getenv('SES_CONFIGURATION_SET')
sqs_queue_url = os.getenv('SQS_QUEUE_URL')

# Create AWS clients
ses_client = boto3.client('ses', region_name=aws_region,
                         aws_access_key_id=aws_access_key,
                         aws_secret_access_key=aws_secret_key)
sns_client = boto3.client('sns', region_name=aws_region,
                         aws_access_key_id=aws_access_key,
                         aws_secret_access_key=aws_secret_key)
sqs_client = boto3.client('sqs', region_name=aws_region,
                         aws_access_key_id=aws_access_key,
                         aws_secret_access_key=aws_secret_key)

def check_ses_configuration():
    """Verify SES configuration set is properly set up with SNS notifications"""
    try:
        # Get the configuration set details
        response = ses_client.describe_configuration_set(
            ConfigurationSetName=ses_config_set,
            ConfigurationSetAttributeNames=['eventDestinations']
        )
        
        logger.info(f"✅ Found SES configuration set: {ses_config_set}")
        
        # Check if we have an SNS event destination
        event_destinations = response.get('EventDestinations', [])
        sns_destinations = [dest for dest in event_destinations 
                           if dest.get('Enabled') and dest.get('MatchingEventTypes') 
                           and 'sns' in dest.get('Name', '').lower()]
        
        if sns_destinations:
            for dest in sns_destinations:
                logger.info(f"✅ Found SNS event destination: {dest.get('Name')}")
                logger.info(f"✅ Event types: {dest.get('MatchingEventTypes')}")
                logger.info(f"✅ SNS topic ARN: {dest.get('SNSDestination', {}).get('TopicARN')}")
                
                # Save the SNS topic ARN
                sns_topic_arn = dest.get('SNSDestination', {}).get('TopicARN')
                if sns_topic_arn:
                    return sns_topic_arn
        else:
            logger.error("❌ No SNS event destinations found!")
            
    except Exception as e:
        logger.error(f"❌ Error checking SES configuration: {str(e)}")
    
    return None

def check_sns_subscription(topic_arn):
    """Verify that SQS is subscribed to the SNS topic"""
    try:
        # List subscriptions for the topic
        response = sns_client.list_subscriptions_by_topic(TopicArn=topic_arn)
        
        subscriptions = response.get('Subscriptions', [])
        logger.info(f"Found {len(subscriptions)} subscriptions for topic {topic_arn}")
        
        # Check if any of them are for our SQS queue
        sqs_subscriptions = [sub for sub in subscriptions if sub.get('Protocol') == 'sqs']
        
        if sqs_subscriptions:
            for sub in sqs_subscriptions:
                logger.info(f"✅ Found SQS subscription: {sub.get('Endpoint')}")
                logger.info(f"✅ Subscription ARN: {sub.get('SubscriptionArn')}")
                return True
        else:
            logger.error("❌ No SQS subscriptions found for this SNS topic!")
            logger.info("Creating a subscription for the SQS queue...")
            
            # Extract queue ARN from the queue URL
            queue_attributes = sqs_client.get_queue_attributes(
                QueueUrl=sqs_queue_url,
                AttributeNames=['QueueArn']
            )
            queue_arn = queue_attributes.get('Attributes', {}).get('QueueArn')
            
            if queue_arn:
                # Create the subscription
                response = sns_client.subscribe(
                    TopicArn=topic_arn,
                    Protocol='sqs',
                    Endpoint=queue_arn
                )
                logger.info(f"✅ Created subscription: {response.get('SubscriptionArn')}")
                return True
            else:
                logger.error("❌ Could not determine SQS queue ARN!")
                
    except Exception as e:
        logger.error(f"❌ Error checking SNS subscription: {str(e)}")
    
    return False

def send_test_email():
    """Send test emails to SES simulator addresses"""
    try:
        # Create a basic email
        test_message = """
        <html>
        <body>
            <h1>Test Email for SES-SNS-SQS Notification Flow</h1>
            <p>This is a test email to verify that notifications are working correctly.</p>
            <p>Timestamp: {}</p>
        </body>
        </html>
        """.format(time.strftime("%Y-%m-%d %H:%M:%S"))
        
        # Define test scenarios
        test_scenarios = [
            {
                'type': 'bounce',
                'email': 'bounce@simulator.amazonses.com',
                'subject': 'Test BOUNCE Notification'
            },
            {
                'type': 'complaint',
                'email': 'complaint@simulator.amazonses.com',
                'subject': 'Test COMPLAINT Notification'
            },
            {
                'type': 'delivery',
                'email': 'success@simulator.amazonses.com',
                'subject': 'Test DELIVERY Notification'
            }
        ]
        
        for scenario in test_scenarios:
            # Send the email
            response = ses_client.send_email(
                Source=sender_email,
                Destination={
                    'ToAddresses': [scenario['email']]
                },
                Message={
                    'Subject': {
                        'Data': scenario['subject']
                    },
                    'Body': {
                        'Html': {
                            'Data': test_message
                        }
                    }
                },
                ConfigurationSetName=ses_config_set
            )
            
            message_id = response.get('MessageId', 'unknown')
            logger.info(f"✅ Sent {scenario['type']} test email with Message ID: {message_id}")
            
            # Wait a short time between sends
            time.sleep(1)
            
    except Exception as e:
        logger.error(f"❌ Error sending test emails: {str(e)}")

def check_sqs_queue():
    """Check the SQS queue for notification messages"""
    try:
        logger.info(f"Checking SQS queue: {sqs_queue_url}")
        
        # Wait longer to allow notifications to arrive
        logger.info("Waiting 30 seconds for notifications to arrive...")
        time.sleep(30)
        
        # Try multiple times to receive messages
        total_messages = []
        for attempt in range(3):
            logger.info(f"Attempt {attempt+1}/3 to receive SQS messages...")
        
            # Try to receive messages with longer wait time
            response = sqs_client.receive_message(
                QueueUrl=sqs_queue_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=20,
                AttributeNames=['All'],
                MessageAttributeNames=['All']
            )
            
            batch_messages = response.get('Messages', [])
            if batch_messages:
                total_messages.extend(batch_messages)
                logger.info(f"Received {len(batch_messages)} messages in batch {attempt+1}")
            else:
                logger.info(f"No messages received in batch {attempt+1}")
                
            # Short pause between attempts
            if attempt < 2:  # Don't sleep after the last attempt
                time.sleep(5)
        
        # Process all collected messages
        messages = total_messages
        logger.info(f"Total received: {len(messages)} messages from SQS queue")
        
        # Display messages
        for i, message in enumerate(messages):
            logger.info(f"Message {i+1}:")
            
            # Parse the message body
            try:
                body = json.loads(message.get('Body', '{}'))
                
                # If this is an SNS message
                if 'Message' in body:
                    # Try to parse the SNS message
                    try:
                        sns_message = json.loads(body.get('Message', '{}'))
                        notification_type = sns_message.get('notificationType') or sns_message.get('eventType')
                        logger.info(f"✅ Notification type: {notification_type}")
                        
                        # Get message details
                        mail_obj = sns_message.get('mail', {})
                        message_id = mail_obj.get('messageId', 'unknown')
                        destination = mail_obj.get('destination', [])
                        
                        logger.info(f"✅ SES Message ID: {message_id}")
                        logger.info(f"✅ Destination: {destination}")
                        
                        # Get specific notification details
                        if notification_type == 'Bounce':
                            bounce_info = sns_message.get('bounce', {})
                            bounce_type = bounce_info.get('bounceType')
                            bounce_subtype = bounce_info.get('bounceSubType')
                            logger.info(f"✅ Bounce type: {bounce_type}, subtype: {bounce_subtype}")
                            
                        elif notification_type == 'Complaint':
                            complaint_info = sns_message.get('complaint', {})
                            complaint_type = complaint_info.get('complaintFeedbackType')
                            logger.info(f"✅ Complaint type: {complaint_type}")
                            
                        elif notification_type == 'Delivery':
                            delivery_info = sns_message.get('delivery', {})
                            recipients = delivery_info.get('recipients', [])
                            logger.info(f"✅ Delivery to: {recipients}")
                            
                    except json.JSONDecodeError:
                        logger.warning(f"⚠️ Could not parse SNS Message: {body.get('Message')[:100]}...")
                        
                else:
                    logger.info(f"Raw message body: {body}")
                    
            except json.JSONDecodeError:
                logger.warning(f"⚠️ Could not parse message body: {message.get('Body')[:100]}...")
                
            # Don't delete the messages so they can be processed by the app
            
    except Exception as e:
        logger.error(f"❌ Error checking SQS queue: {str(e)}")

def run_verification():
    """Run the complete verification process"""
    logger.info("=== STARTING SES-SNS-SQS VERIFICATION ===")
    
    # Step 1: Check SES configuration
    logger.info("\n=== CHECKING SES CONFIGURATION ===")
    sns_topic_arn = check_ses_configuration()
    
    if not sns_topic_arn:
        logger.error("❌ Cannot continue without an SNS topic!")
        return
    
    # Step 2: Check SNS subscription
    logger.info("\n=== CHECKING SNS SUBSCRIPTION ===")
    subscription_ok = check_sns_subscription(sns_topic_arn)
    
    if not subscription_ok:
        logger.error("❌ SNS subscription check failed!")
        return
    
    # Step 3: Send test emails
    logger.info("\n=== SENDING TEST EMAILS ===")
    send_test_email()
    
    # Step 4: Check SQS queue
    logger.info("\n=== CHECKING SQS QUEUE ===")
    check_sqs_queue()
    
    logger.info("\n=== VERIFICATION COMPLETE ===")
    logger.info("Check your app logs to see if the SQS messages are being processed correctly!")

if __name__ == "__main__":
    run_verification()
