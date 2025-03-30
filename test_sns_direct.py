#!/usr/bin/env python
"""
A script to test sending an SNS notification directly to the application webhook.
"""
import os
import json
import logging
import boto3
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def test_sns_direct(topic_arn=None):
    """
    Send a test message directly to an SNS topic or create a test bounce notification.
    
    Args:
        topic_arn: The ARN of the SNS topic to publish to. If None, user will be prompted.
    """
    # Create boto3 SNS client
    sns_client = boto3.client(
        'sns',
        aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
        region_name=os.environ.get('AWS_REGION') or 'us-east-2'
    )
    
    # List available topics if topic_arn is not provided
    if not topic_arn:
        logger.info("Listing available SNS topics...")
        topics = sns_client.list_topics()
        
        if not topics.get('Topics'):
            logger.error("No SNS topics found in your account. Please create a topic first.")
            return
        
        print("Available SNS topics:")
        for i, topic in enumerate(topics.get('Topics', [])):
            print(f"{i+1}. {topic['TopicArn']}")
        
        selection = input("Enter the number of the topic to use or paste a topic ARN: ")
        
        if selection.isdigit() and 1 <= int(selection) <= len(topics.get('Topics')):
            topic_arn = topics['Topics'][int(selection)-1]['TopicArn']
        elif selection.startswith('arn:aws:sns:'):
            topic_arn = selection
        else:
            logger.error("Invalid selection. Exiting.")
            return
    
    logger.info(f"Using SNS topic: {topic_arn}")
    
    # Create a sample SES bounce notification
    bounce_notification = {
        "notificationType": "Bounce",
        "bounce": {
            "bounceType": "Permanent",
            "bounceSubType": "General",
            "bouncedRecipients": [
                {
                    "emailAddress": "bounce@simulator.amazonses.com",
                    "action": "failed",
                    "status": "5.1.1",
                    "diagnosticCode": "Test bounce diagnostic code"
                }
            ],
            "timestamp": "2025-03-28T23:06:35.000Z",
            "feedbackId": "0100017XXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX-000000"
        },
        "mail": {
            "timestamp": "2025-03-28T23:06:34.000Z",
            "source": "sender@yourdomain.com",
            "sourceArn": "arn:aws:ses:us-east-2:123456789012:identity/yourdomain.com",
            "sourceIp": "192.0.2.0",
            "sendingAccountId": "123456789012",
            "messageId": "010f0195df0118c9-f4c16128-ea6c-4eb5-9dc7-0dc63a590db7-000000",
            "destination": [
                "bounce@simulator.amazonses.com"
            ],
            "headersTruncated": False,
            "headers": [
                {
                    "name": "From",
                    "value": "sender@yourdomain.com"
                },
                {
                    "name": "To",
                    "value": "bounce@simulator.amazonses.com"
                },
                {
                    "name": "Subject",
                    "value": "Test Bounce Email"
                }
            ],
            "commonHeaders": {
                "from": [
                    "sender@yourdomain.com"
                ],
                "to": [
                    "bounce@simulator.amazonses.com"
                ],
                "subject": "Test Bounce Email"
            }
        }
    }
    
    # Publish to the topic
    try:
        response = sns_client.publish(
            TopicArn=topic_arn,
            Message=json.dumps({'default': json.dumps(bounce_notification)}),
            MessageStructure='json'
        )
        
        logger.info(f"Message published to SNS topic. MessageId: {response['MessageId']}")
        logger.info("Check your application logs to see if the notification was received and processed")
        logger.info("If it wasn't received, check AWS SNS console to make sure there's a confirmed subscription for your ngrok URL.")
        
    except Exception as e:
        logger.error(f"Error publishing to SNS: {e}")

if __name__ == "__main__":
    test_sns_direct()
