"""
Test Bounce and Delivery Status Updates

This script tests whether bounce and delivery notifications from AWS SES 
are correctly updating the recipient status in the database.

It uses the AWS SES simulator addresses to generate bounces and successful deliveries,
then verifies the database was updated correctly.
"""

import os
import sys
import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add the parent directory to sys.path to import app modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import app modules with lazy initialization pattern
from app import get_app
from models import EmailCampaign, EmailRecipient, db

# Test email addresses from Amazon SES Simulator
# https://docs.aws.amazon.com/ses/latest/dg/send-email-simulator.html
TEST_EMAILS = {
    'success': 'success@simulator.amazonses.com',  # Successful delivery
    'bounce': 'bounce@simulator.amazonses.com',    # Hard bounce
    'complaint': 'complaint@simulator.amazonses.com',  # Complaint
}

def create_test_campaign(app):
    """Create a test campaign for bounce/delivery testing"""
    with app.app_context():
        # Check if a test campaign already exists
        campaign = EmailCampaign.query.filter_by(name='Bounce Test Campaign').first()
        
        if not campaign:
            logger.info("Creating test campaign")
            campaign = EmailCampaign(
                name='Bounce Test Campaign',
                subject='Test Email for Bounce/Delivery Verification',
                body_html='<p>This is a test email to verify bounce and delivery handling.</p>',
                body_text='This is a test email to verify bounce and delivery handling.',
                sender_name='Bounce Test',
                sender_email=os.environ.get('SENDER_EMAIL'),
                scheduled_time=datetime.now(),
                status='draft'
            )
            db.session.add(campaign)
            db.session.commit()
            logger.info(f"Created test campaign with ID: {campaign.id}")
        else:
            logger.info(f"Using existing test campaign with ID: {campaign.id}")
            
        return campaign

def create_test_recipients(app, campaign):
    """Create test recipients using SES simulator addresses"""
    with app.app_context():
        # Clear any existing test recipients for this campaign
        EmailRecipient.query.filter_by(campaign_id=campaign.id).delete()
        db.session.commit()
        
        # Create new test recipients
        recipients = []
        for test_type, email in TEST_EMAILS.items():
            recipient = EmailRecipient(
                campaign_id=campaign.id,
                email=email,
                name=f"Test {test_type.capitalize()}",
                status='pending',
                is_test=True
            )
            db.session.add(recipient)
            recipients.append(recipient)
        
        db.session.commit()
        logger.info(f"Created {len(recipients)} test recipients")
        return recipients

def send_test_emails(app, campaign):
    """Send test emails to the simulator addresses"""
    with app.app_context():
        # Query for fresh recipient objects within the context
        fresh_recipients = EmailRecipient.query.filter_by(campaign_id=campaign.id).all()
        email_service = app.get_email_service()
        
        for recipient in fresh_recipients:
            logger.info(f"Sending test email to {recipient.email}")
            
            # Get recipient's custom data
            custom_data = {}
            if hasattr(recipient, 'custom_data') and recipient.custom_data:
                try:
                    custom_data = recipient.get_custom_data()
                except:
                    pass
            
            # Prepare template data
            template_data = {
                'name': recipient.name or '',
                'email': recipient.email,
                **custom_data
            }
            
            # Send email with template
            message_id = email_service.send_template_email(
                recipient=recipient.email,
                subject=campaign.subject,
                template_html=campaign.body_html,
                template_text=campaign.body_text,
                template_data=template_data,
                sender_name=campaign.sender_name,
                sender=campaign.sender_email
            )
            
            if message_id:
                # Clean message ID format if needed
                if message_id.startswith('<') and message_id.endswith('>'):
                    message_id = message_id[1:-1]
                
                # Update recipient status
                recipient.status = 'sent'
                recipient.sent_at = datetime.now()
                recipient.message_id = message_id
                recipient.delivery_status = 'sent'
                logger.info(f"Email sent to {recipient.email}, message ID: {message_id}")
            else:
                recipient.status = 'failed'
                recipient.error_message = 'Failed to send email'
                logger.error(f"Failed to send email to {recipient.email}")
            
            db.session.commit()

def check_status_updates(app, campaign, wait_time=30):
    """
    Check if recipient statuses were updated correctly after the specified wait time.
    
    This assumes that SNS notifications have been received and processed by the application.
    """
    logger.info(f"Waiting {wait_time} seconds for SNS notifications...")
    time.sleep(wait_time)
    
    with app.app_context():
        # Refresh recipients from database
        recipients = EmailRecipient.query.filter_by(campaign_id=campaign.id).all()
        
        success = True
        for recipient in recipients:
            logger.info(f"Recipient {recipient.email}: status={recipient.status}, delivery_status={recipient.delivery_status}")
            
            # Check if status was updated correctly based on email type
            if 'success' in recipient.email and recipient.delivery_status != 'delivered':
                logger.error(f"ERROR: Success email {recipient.email} should have delivery_status='delivered', but has '{recipient.delivery_status}'")
                success = False
            
            if 'bounce' in recipient.email and recipient.delivery_status != 'bounced':
                logger.error(f"ERROR: Bounce email {recipient.email} should have delivery_status='bounced', but has '{recipient.delivery_status}'")
                success = False
            
            if 'complaint' in recipient.email and recipient.delivery_status != 'complained':
                logger.error(f"ERROR: Complaint email {recipient.email} should have delivery_status='complained', but has '{recipient.delivery_status}'")
                success = False
                
            # Log details that might help debug issues
            logger.info(f"  Message ID: {recipient.message_id}")
            logger.info(f"  Bounce Type: {recipient.bounce_type}")
            logger.info(f"  Bounce Time: {recipient.bounce_time}")
            logger.info(f"  Error: {recipient.error_message}")
        
        if success:
            logger.info("SUCCESS: All recipient statuses were updated correctly!")
        else:
            logger.error("FAILURE: Some recipient statuses were not updated correctly.")
            
        return success

def run_test():
    """Run the complete bounce and delivery test"""
    logger.info("Starting bounce and delivery test")
    
    # Get Flask app with lazy initialization pattern
    app = get_app()
    
    try:
        # Create test campaign and recipients
        campaign = create_test_campaign(app)
        recipients = create_test_recipients(app, campaign)
        
        # Send test emails
        send_test_emails(app, campaign)
        
        # Check for status updates
        success = check_status_updates(app, campaign)
        
        if success:
            logger.info("Test completed successfully!")
            return 0
        else:
            logger.error("Test failed! Status updates not working correctly.")
            return 1
            
    except Exception as e:
        logger.exception(f"Error during test: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(run_test())
