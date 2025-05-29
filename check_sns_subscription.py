import boto3
import json
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
topic_arn = os.getenv('SNS_TOPIC_ARN', 'arn:aws:sns:us-east-2:109869386849:ses-email-bulk-scheduler-config-notifications')
sqs_queue_url = os.getenv('SQS_QUEUE_URL', '')
sqs_queue_arn = sqs_queue_url.replace('https://sqs.us-east-2.amazonaws.com/109869386849/', 'arn:aws:sqs:us-east-2:109869386849:')

def check_sns_subscriptions():
    """Check SNS topic subscriptions"""
    try:
        # Create AWS SNS client
        sns_client = boto3.client('sns', region_name=aws_region,
                                aws_access_key_id=aws_access_key,
                                aws_secret_access_key=aws_secret_key)
        
        logger.info(f"Checking subscriptions for SNS topic: {topic_arn}")
        
        # List subscriptions for the topic
        response = sns_client.list_subscriptions_by_topic(
            TopicArn=topic_arn
        )
        
        subscriptions = response.get('Subscriptions', [])
        
        if not subscriptions:
            logger.warning(f"⚠️ No subscriptions found for SNS topic: {topic_arn}")
            logger.info(f"Creating new subscription for SQS queue: {sqs_queue_arn}")
            
            try:
                # Create new subscription for SQS queue
                subscription_response = sns_client.subscribe(
                    TopicArn=topic_arn,
                    Protocol='sqs',
                    Endpoint=sqs_queue_arn
                )
                subscription_arn = subscription_response.get('SubscriptionArn')
                logger.info(f"✅ Created new subscription: {subscription_arn}")
                return True
            except Exception as e:
                logger.error(f"❌ Error creating subscription: {str(e)}")
                return False
            
        else:
            logger.info(f"Found {len(subscriptions)} subscription(s):")
            sqs_subscription_found = False
            
            for sub in subscriptions:
                sub_arn = sub.get('SubscriptionArn')
                sub_endpoint = sub.get('Endpoint')
                sub_protocol = sub.get('Protocol')
                sub_status = 'PendingConfirmation' if sub_arn == 'PendingConfirmation' else 'Confirmed'
                
                logger.info(f"  Subscription: {sub_arn}")
                logger.info(f"    Protocol: {sub_protocol}")
                logger.info(f"    Endpoint: {sub_endpoint}")
                logger.info(f"    Status: {sub_status}")
                
                # Check if this is our SQS queue subscription
                if sub_protocol == 'sqs' and sqs_queue_arn in sub_endpoint:
                    sqs_subscription_found = True
                    
                    if sub_status == 'PendingConfirmation':
                        logger.warning(f"⚠️ SQS subscription needs confirmation")
                        
                        # Try to confirm subscription
                        try:
                            confirm_response = sns_client.confirm_subscription(
                                TopicArn=topic_arn,
                                Token=sub_arn
                            )
                            logger.info(f"✅ Confirmed subscription: {confirm_response.get('SubscriptionArn')}")
                        except Exception as e:
                            logger.error(f"❌ Error confirming subscription: {str(e)}")
            
            if not sqs_subscription_found:
                logger.warning(f"⚠️ No SQS subscription found for queue: {sqs_queue_arn}")
                logger.info(f"Creating new subscription for SQS queue: {sqs_queue_arn}")
                
                try:
                    # Create new subscription for SQS queue
                    subscription_response = sns_client.subscribe(
                        TopicArn=topic_arn,
                        Protocol='sqs',
                        Endpoint=sqs_queue_arn
                    )
                    subscription_arn = subscription_response.get('SubscriptionArn')
                    logger.info(f"✅ Created new subscription: {subscription_arn}")
                    return True
                except Exception as e:
                    logger.error(f"❌ Error creating subscription: {str(e)}")
                    return False
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Error checking SNS subscriptions: {str(e)}")
        return False

def check_sqs_queue():
    """Check SQS queue status and permissions"""
    try:
        # Create AWS SQS client
        sqs_client = boto3.client('sqs', region_name=aws_region,
                                aws_access_key_id=aws_access_key,
                                aws_secret_access_key=aws_secret_key)
        
        logger.info(f"Checking SQS queue: {sqs_queue_url}")
        
        # Get queue attributes
        response = sqs_client.get_queue_attributes(
            QueueUrl=sqs_queue_url,
            AttributeNames=['All']
        )
        
        attributes = response.get('Attributes', {})
        
        logger.info(f"SQS Queue Attributes:")
        logger.info(f"  Queue ARN: {attributes.get('QueueArn')}")
        logger.info(f"  Approx. Messages Available: {attributes.get('ApproximateNumberOfMessages')}")
        logger.info(f"  Visibility Timeout: {attributes.get('VisibilityTimeout')}")
        
        # Check queue policy
        policy = attributes.get('Policy')
        
        if policy:
            policy_json = json.loads(policy)
            logger.info(f"Queue Policy:")
            
            statements = policy_json.get('Statement', [])
            sns_allowed = False
            
            for statement in statements:
                effect = statement.get('Effect')
                principal = statement.get('Principal', {})
                action = statement.get('Action')
                resource = statement.get('Resource')
                
                logger.info(f"  Statement:")
                logger.info(f"    Effect: {effect}")
                logger.info(f"    Principal: {principal}")
                logger.info(f"    Action: {action}")
                logger.info(f"    Resource: {resource}")
                
                # Check if SNS is allowed to send messages
                if (effect == 'Allow' and 
                    (principal.get('Service') == 'sns.amazonaws.com' or 
                     'sns.amazonaws.com' in str(principal)) and
                    ('sqs:SendMessage' in action or action == 'sqs:SendMessage')):
                    sns_allowed = True
            
            if not sns_allowed:
                logger.warning("⚠️ Queue policy does not allow SNS to send messages!")
                logger.info("Please update the queue policy to allow SNS to send messages")
        else:
            logger.warning("⚠️ No queue policy found!")
            logger.info("Queue needs a policy to allow SNS to send messages")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error checking SQS queue: {str(e)}")
        return False

if __name__ == "__main__":
    print("=== CHECKING SNS-SQS CONFIGURATION ===")
    
    # Check SNS subscriptions
    print("\n=== SNS SUBSCRIPTIONS ===")
    sns_check = check_sns_subscriptions()
    
    # Check SQS queue
    print("\n=== SQS QUEUE STATUS ===")
    sqs_check = check_sqs_queue()
    
    # Summary
    print("\n=== CONFIGURATION CHECK SUMMARY ===")
    if sns_check and sqs_check:
        print("✅ SNS and SQS configuration checks completed")
        print("If issues persist, check application logs and AWS permissions")
    else:
        print("⚠️ Issues found with SNS-SQS configuration")
        print("Review the logs above and fix the identified issues")
