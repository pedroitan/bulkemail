import boto3
import os
import time
import json
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# AWS credentials
aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
aws_region = os.getenv('AWS_REGION', 'us-east-2')
sender_email = os.getenv('SENDER_EMAIL')

# Invalid email to test
INVALID_EMAIL = "psodli@gmalihs.com"

def send_test_email():
    """Send a test email to an invalid address."""
    try:
        # Create SES client
        ses_client = boto3.client(
            'ses',
            region_name=aws_region,
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key
        )
        
        # Email content
        subject = "Test Email to Invalid Domain"
        body_html = """
        <html>
        <body>
            <h1>Test Email</h1>
            <p>This is a test email sent to an invalid domain to test bounce handling.</p>
        </body>
        </html>
        """
        body_text = "This is a test email sent to an invalid domain to test bounce handling."
        
        # Send the email - without specifying a configuration set
        email_args = {
            'Source': sender_email,
            'Destination': {
                'ToAddresses': [INVALID_EMAIL]
            },
            'Message': {
                'Subject': {'Data': subject},
                'Body': {
                    'Text': {'Data': body_text},
                    'Html': {'Data': body_html}
                }
            }
        }
        
        # Ask user if they want to specify a configuration set
        use_config = input("Do you want to use a configuration set? (yes/no): ").lower().strip()
        if use_config == 'yes':
            config_name = input("Enter your configuration set name: ").strip()
            if config_name:
                email_args['ConfigurationSetName'] = config_name
                logger.info(f"Using configuration set: {config_name}")
        
        response = ses_client.send_email(**email_args)
        
        message_id = response['MessageId']
        logger.info(f"Email sent to {INVALID_EMAIL}, Message ID: {message_id}")
        return message_id
        
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        return None

def check_bounce_notification(message_id):
    """Tell the user to check their app for bounce notifications."""
    logger.info(f"Sent test email with Message ID: {message_id}")
    logger.info("Now watching for bounce notifications...")
    logger.info("Check your Flask app logs for incoming SNS notifications about this bounce.")
    logger.info("Typically, bounces for invalid domains may come back within a few minutes.")
    logger.info("However, some mail servers might delay bounce notifications or not send them at all.")

if __name__ == "__main__":
    logger.info(f"Sending test email to invalid address: {INVALID_EMAIL}")
    message_id = send_test_email()
    
    if message_id:
        check_bounce_notification(message_id)
