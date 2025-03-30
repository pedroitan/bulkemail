#!/usr/bin/env python
"""
A script to test sending an email to the bounce simulator to verify bounce handling
"""
import logging
import os
import sys
from dotenv import load_dotenv
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Load environment variables
load_dotenv()

def send_test_bounce():
    """Send a test email to the bounce simulator with appropriate tracking"""
    # Import here to respect the application's lazy initialization pattern
    from email_service import SESEmailService
    from models import db, EmailRecipient, EmailCampaign
    from app import create_app
    
    # Create and configure the Flask app
    app = create_app()
    
    with app.app_context():
        # Create a test recipient directly in the database
        bounce_email = "bounce@simulator.amazonses.com"
        
        # Check if a test recipient already exists
        existing = EmailRecipient.query.filter_by(
            email=bounce_email, 
            is_test=True
        ).first()
        
        if existing:
            # Update the existing test recipient
            recipient = existing
            recipient.status = "pending"
            recipient.delivery_status = None
            recipient.bounce_type = None
            recipient.bounce_subtype = None
            recipient.bounce_time = None
            recipient.bounce_diagnostic = None
            recipient.sent_at = None
            logger.info(f"Updated existing test recipient: {recipient.id}")
        else:
            # Create a new test recipient
            recipient = EmailRecipient(
                campaign_id=1,  # Using the first campaign
                email=bounce_email,
                name="Bounce Test",
                status="pending",
                is_test=True
            )
            db.session.add(recipient)
        
        db.session.commit()
        logger.info(f"Test recipient ID: {recipient.id}")
        
        # Create email service
        email_service = SESEmailService(
            aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
            region_name=os.environ.get('AWS_REGION') or 'us-east-2'
        )
        
        # Send the test email
        logger.info(f"Sending test email to {bounce_email}...")
        result = email_service.send_email(
            recipient=bounce_email,
            subject="Bounce Test [" + datetime.now().strftime("%H:%M:%S") + "]",
            body_html="<html><body><h1>Test Bounce</h1><p>This is a test email to trigger a bounce notification.</p></body></html>",
            body_text="Test Bounce\n\nThis is a test email to trigger a bounce notification.",
            sender_name="Bounce Tracker Test"
        )
        
        if result.get('success'):
            # Update the recipient with the message ID for tracking
            recipient.message_id = result.get('message_id')
            recipient.status = 'sent'
            recipient.sent_at = datetime.now()
            recipient.delivery_status = 'sent'
            db.session.commit()
            
            logger.info(f"Test email sent successfully. Message ID: {recipient.message_id}")
            logger.info(f"Recipient ID: {recipient.id} updated with message ID")
            logger.info("Check your application logs for bounce notification processing...")
            logger.info("Wait about 30-60 seconds for AWS to process the bounce and send the notification")
        else:
            logger.error(f"Failed to send test email: {result}")

if __name__ == "__main__":
    send_test_bounce()
