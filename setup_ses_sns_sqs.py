"""
Setup script for SES-SNS-SQS notification path

This script will:
1. Create or verify an SNS topic for SES notifications
2. Subscribe your SQS queue to the SNS topic
3. Configure your SES configuration set to send events to the SNS topic
"""

import os
import json
import logging
import boto3
import time
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class NotificationPathSetup:
    def __init__(self):
        """Initialize AWS clients"""
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
        
        self.sns_client = boto3.client(
            'sns',
            region_name=self.region,
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
        )
        
        # Set topic name based on configuration set
        self.topic_name = f"ses-{self.config_set}-notifications"
    
    def setup_sns_topic(self):
        """Create or find SNS topic for SES notifications"""
        logger.info("=== SETTING UP SNS TOPIC ===")
        
        # Check if topic already exists
        topics = self.sns_client.list_topics().get('Topics', [])
        topic_arn = None
        
        for topic in topics:
            arn = topic.get('TopicArn', '')
            if self.topic_name in arn:
                topic_arn = arn
                logger.info(f"Found existing SNS topic: {topic_arn}")
                break
        
        # Create topic if it doesn't exist
        if not topic_arn:
            response = self.sns_client.create_topic(Name=self.topic_name)
            topic_arn = response.get('TopicArn')
            logger.info(f"Created new SNS topic: {topic_arn}")
        
        # Make sure topic policy allows SES to publish
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "ses.amazonaws.com"
                    },
                    "Action": "sns:Publish",
                    "Resource": topic_arn,
                    "Condition": {
                        "StringEquals": {
                            "aws:SourceAccount": topic_arn.split(':')[4]
                        }
                    }
                }
            ]
        }
        
        # Set topic policy
        self.sns_client.set_topic_attributes(
            TopicArn=topic_arn,
            AttributeName='Policy',
            AttributeValue=json.dumps(policy_document)
        )
        logger.info("✅ SNS topic policy updated to allow SES publishing")
        
        return topic_arn
    
    def subscribe_sqs_to_sns(self, topic_arn):
        """Subscribe SQS queue to SNS topic"""
        logger.info("=== SUBSCRIBING SQS QUEUE TO SNS TOPIC ===")
        
        if not self.queue_url:
            logger.error("Queue URL not provided in environment variables")
            return False
        
        # Get queue ARN
        queue_attrs = self.sqs_client.get_queue_attributes(
            QueueUrl=self.queue_url,
            AttributeNames=['QueueArn']
        )
        queue_arn = queue_attrs.get('Attributes', {}).get('QueueArn')
        
        if not queue_arn:
            logger.error("Could not get queue ARN")
            return False
            
        logger.info(f"Queue ARN: {queue_arn}")
        
        # Check existing subscriptions first
        subscriptions = self.sns_client.list_subscriptions_by_topic(
            TopicArn=topic_arn
        ).get('Subscriptions', [])
        
        for sub in subscriptions:
            if sub.get('Protocol') == 'sqs' and sub.get('Endpoint') == queue_arn:
                logger.info(f"SQS queue already subscribed with ARN: {sub.get('SubscriptionArn')}")
                return True
        
        # Create new subscription
        response = self.sns_client.subscribe(
            TopicArn=topic_arn,
            Protocol='sqs',
            Endpoint=queue_arn,
            ReturnSubscriptionArn=True
        )
        
        subscription_arn = response.get('SubscriptionArn')
        logger.info(f"✅ Subscribed SQS queue to SNS topic: {subscription_arn}")
        
        # Update queue policy to allow SNS messages
        try:
            # Get current policy
            policy_response = self.sqs_client.get_queue_attributes(
                QueueUrl=self.queue_url,
                AttributeNames=['Policy']
            )
            
            # Parse existing policy or create new one
            if 'Policy' in policy_response.get('Attributes', {}):
                policy = json.loads(policy_response['Attributes']['Policy'])
            else:
                policy = {
                    "Version": "2012-10-17",
                    "Id": f"{queue_arn}/SQSDefaultPolicy",
                    "Statement": []
                }
            
            # Check if policy already has SNS permissions
            sns_statement_exists = False
            for statement in policy.get('Statement', []):
                if (statement.get('Effect') == 'Allow' and 
                    'Service' in statement.get('Principal', {}) and 
                    statement.get('Principal', {}).get('Service') == 'sns.amazonaws.com'):
                    sns_statement_exists = True
                    break
            
            # Add SNS permission if needed
            if not sns_statement_exists:
                policy['Statement'].append({
                    "Sid": "AllowSNSPublish",
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "sns.amazonaws.com"
                    },
                    "Action": "sqs:SendMessage",
                    "Resource": queue_arn,
                    "Condition": {
                        "ArnEquals": {
                            "aws:SourceArn": topic_arn
                        }
                    }
                })
                
                # Update queue policy
                self.sqs_client.set_queue_attributes(
                    QueueUrl=self.queue_url,
                    Attributes={
                        'Policy': json.dumps(policy)
                    }
                )
                logger.info("✅ Updated SQS queue policy to allow SNS messages")
            else:
                logger.info("SQS queue policy already allows SNS messages")
                
            return True
                
        except Exception as e:
            logger.error(f"Error updating SQS policy: {str(e)}")
            return False
    
    def configure_ses_event_destination(self, topic_arn):
        """Configure SES to send events to SNS topic"""
        logger.info("=== CONFIGURING SES EVENT DESTINATION ===")
        
        if not self.config_set:
            logger.error("Configuration set not provided in environment variables")
            return False
            
        try:
            # Check if config set exists
            config_sets = self.ses_client.list_configuration_sets().get('ConfigurationSets', [])
            config_set_exists = False
            
            for config in config_sets:
                if config.get('Name') == self.config_set:
                    config_set_exists = True
                    break
            
            if not config_set_exists:
                logger.error(f"Configuration set {self.config_set} does not exist")
                return False
                
            # Check existing event destinations
            try:
                destinations = self.ses_client.describe_configuration_set(
                    ConfigurationSetName=self.config_set,
                    ConfigurationSetAttributeNames=['eventDestinations']
                ).get('EventDestinations', [])
                
                sns_destination_exists = False
                for dest in destinations:
                    if (dest.get('Name') == 'SNSDestination' and 
                        dest.get('Enabled', False) and 
                        dest.get('EventDestinationType') == 'SNS'):
                        sns_destination_exists = True
                        logger.info("SES already has SNS event destination configured")
                        break
                
                if not sns_destination_exists:
                    # Create new event destination
                    self.ses_client.create_configuration_set_event_destination(
                        ConfigurationSetName=self.config_set,
                        EventDestination={
                            'Name': 'SNSDestination',
                            'Enabled': True,
                            'MatchingEventTypes': [
                                'send', 'reject', 'bounce', 'complaint', 
                                'delivery', 'open', 'click', 'renderingFailure'
                            ],
                            'SNSDestination': {
                                'TopicARN': topic_arn
                            }
                        }
                    )
                    logger.info(f"✅ Created SES event destination to SNS topic {topic_arn}")
                
                return True
                
            except Exception as e:
                if 'describe_configuration_set' in str(e):
                    logger.warning("Your IAM user doesn't have permission to describe configuration sets")
                    logger.warning("We'll try to create the event destination anyway")
                    
                    # Try to create the event destination anyway
                    try:
                        self.ses_client.create_configuration_set_event_destination(
                            ConfigurationSetName=self.config_set,
                            EventDestination={
                                'Name': 'SNSDestination',
                                'Enabled': True,
                                'MatchingEventTypes': [
                                    'send', 'reject', 'bounce', 'complaint', 
                                    'delivery', 'open', 'click', 'renderingFailure'
                                ],
                                'SNSDestination': {
                                    'TopicARN': topic_arn
                                }
                            }
                        )
                        logger.info(f"✅ Created SES event destination to SNS topic {topic_arn}")
                        return True
                    except Exception as create_error:
                        logger.error(f"Error creating event destination: {str(create_error)}")
                        return False
                else:
                    logger.error(f"Error checking event destinations: {str(e)}")
                    return False
                
        except Exception as e:
            logger.error(f"Error configuring SES event destination: {str(e)}")
            return False
    
    def run_setup(self):
        """Run the complete setup process"""
        logger.info("Starting SES-SNS-SQS notification path setup...")
        
        # Step 1: Set up SNS topic
        topic_arn = self.setup_sns_topic()
        if not topic_arn:
            logger.error("Failed to set up SNS topic")
            return False
        
        # Step 2: Subscribe SQS to SNS
        if not self.subscribe_sqs_to_sns(topic_arn):
            logger.error("Failed to subscribe SQS to SNS")
            return False
        
        # Step 3: Configure SES event destination
        if not self.configure_ses_event_destination(topic_arn):
            logger.error("Failed to configure SES event destination")
            return False
        
        logger.info("\n=== SETUP COMPLETE ===")
        logger.info(f"SES Configuration Set: {self.config_set}")
        logger.info(f"SNS Topic ARN: {topic_arn}")
        logger.info(f"SQS Queue URL: {self.queue_url}")
        logger.info("\nYour SES-SNS-SQS notification path is now set up!")
        logger.info("To test it, send an email to bounce@simulator.amazonses.com")
        
        return True

if __name__ == "__main__":
    setup = NotificationPathSetup()
    setup.run_setup()
