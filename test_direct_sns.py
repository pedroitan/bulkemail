import boto3
import json
import time
import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_direct_sns_notification():
    """Test direct SNS notification delivery to your webhook endpoint"""
    
    # AWS configuration
    aws_region = os.getenv('AWS_REGION', 'us-east-2')
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    topic_arn = os.getenv('SNS_TOPIC_ARN', 'arn:aws:sns:us-east-2:109869386849:ses-email-bulk-scheduler-config-notifications')
    
    # Create AWS SNS client
    sns_client = boto3.client('sns', region_name=aws_region,
                             aws_access_key_id=aws_access_key,
                             aws_secret_access_key=aws_secret_key)
    
    logger.info(f"Testing direct SNS notification delivery to topic: {topic_arn}")
    
    # Prepare a test notification in the format of an SES bounce notification
    notification = {
        "notificationType": "Bounce",
        "bounce": {
            "bounceType": "Permanent",
            "bounceSubType": "General",
            "bouncedRecipients": [
                {
                    "emailAddress": "bounce@example.com",
                    "action": "failed",
                    "status": "5.1.1",
                    "diagnosticCode": "Test bounce message"
                }
            ],
            "timestamp": "2025-03-31T23:45:00.000Z",
            "feedbackId": "test-feedback-id-direct-sns"
        },
        "mail": {
            "timestamp": "2025-03-31T23:40:00.000Z",
            "messageId": "test-message-id-direct-sns",
            "source": os.getenv('SENDER_EMAIL', 'test@example.com'),
            "sourceArn": "arn:aws:ses:us-east-2:109869386849:identity/test@example.com",
            "destination": ["bounce@example.com"]
        }
    }
    
    # A simple test message as well
    test_message = {
        "default": "Test notification from SNS",
        "email": json.dumps(notification)
    }
    
    try:
        # Publish message to SNS topic
        response = sns_client.publish(
            TopicArn=topic_arn,
            Message=json.dumps(notification),
            MessageStructure='string'
        )
        
        message_id = response.get('MessageId')
        logger.info(f"✅ Successfully published test message to SNS: {message_id}")
        
        # Wait a bit for the notification to be processed
        logger.info("Waiting 5 seconds for notification processing...")
        time.sleep(5)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error publishing to SNS: {str(e)}")
        return False

if __name__ == "__main__":
    print("=== TESTING DIRECT SNS NOTIFICATION DELIVERY ===")
    success = test_direct_sns_notification()
    if success:
        print("✅ Test completed. Check your application logs for notification processing.")
    else:
        print("❌ Test failed. See error messages above.")
