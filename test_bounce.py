#!/usr/bin/env python
"""
A simple script to test the Amazon SES bounce simulator
"""
import sys
import os
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Load environment variables
load_dotenv()

def test_bounce_simulator():
    """Send a test email to the Amazon SES bounce simulator"""
    from email_service import SESEmailService
    
    email_service = SESEmailService(
        aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
        region_name=os.environ.get('AWS_REGION') or 'us-east-2'
    )
    
    # Send to bounce simulator
    bounce_result = email_service.send_email(
        recipient='bounce@simulator.amazonses.com',
        subject='Test Bounce Email',
        body_html='<html><body><h1>Test Bounce</h1><p>This is a test email to the SES bounce simulator.</p></body></html>',
        body_text='Test Bounce\n\nThis is a test email to the SES bounce simulator.',
        sender_name='Bounce Test'
    )
    
    logger.info(f"Bounce test email sent: {bounce_result}")
    
    # Send to complaint simulator
    complaint_result = email_service.send_email(
        recipient='complaint@simulator.amazonses.com',
        subject='Test Complaint Email',
        body_html='<html><body><h1>Test Complaint</h1><p>This is a test email to the SES complaint simulator.</p></body></html>',
        body_text='Test Complaint\n\nThis is a test email to the SES complaint simulator.',
        sender_name='Complaint Test'
    )
    
    logger.info(f"Complaint test email sent: {complaint_result}")
    
    # Print message to check logs
    logger.info("Check your application logs for notification processing!")
    logger.info("Wait about 30 seconds for AWS to process and send notifications")

if __name__ == '__main__':
    test_bounce_simulator()
