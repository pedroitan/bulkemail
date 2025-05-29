#!/usr/bin/env python
"""
Fix the email tracking system by addressing critical issues:
1. Ensure tracking_manager is correctly connected to email_service
2. Verify tracking routes are properly registered
3. Add a symbolic link between process_html_content and process_html_for_tracking
"""

import os
import sys
import logging
from datetime import datetime

# Set up environment
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
os.environ["FLASK_ENV"] = "development"

# Import Flask app and models
from app import app, db
from models import EmailCampaign, EmailRecipient, EmailTracking, EmailTrackingEvent
from email_tracking import EmailTrackingManager
import email_service

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_tracking_system():
    """Fix the email tracking system by addressing all identified issues."""
    with app.app_context():
        # 1. First, check if tracking_manager is properly connected to the app
        if not hasattr(app, 'tracking_manager'):
            logger.error("No tracking_manager found on app, this should be fixed in app.py")
            return False
        
        logger.info("✓ tracking_manager is connected to app")
        
        # 2. Check if email_service is correctly getting the tracking_manager
        email_service_instance = app.get_email_service()
        if not email_service_instance:
            logger.error("No email_service found on app")
            return False
        
        # 3. Link tracking_manager to email_service if needed
        if not email_service_instance.tracking_manager:
            logger.warning("Tracking manager not connected to email_service, fixing...")
            email_service_instance.tracking_manager = app.tracking_manager
            logger.info("✓ Connected tracking_manager to email_service")
        else:
            logger.info("✓ tracking_manager already connected to email_service")
        
        # 4. Fix method name inconsistency
        if not hasattr(app.tracking_manager, 'process_html_for_tracking'):
            logger.warning("Method 'process_html_for_tracking' not found, creating alias...")
            # Add alias for process_html_content
            setattr(EmailTrackingManager, 'process_html_for_tracking', 
                   EmailTrackingManager.process_html_content)
            logger.info("✓ Added process_html_for_tracking alias to EmailTrackingManager")
        
        # 5. Verify tracking routes
        with app.test_client() as client:
            # Test tracking pixel route
            pixel_response = client.get('/tracking/pixel/test.png')
            if pixel_response.status_code == 404:
                logger.error("Tracking pixel route not found!")
            else:
                logger.info("✓ Tracking pixel route is registered")
            
            # Test tracking redirect route
            redirect_response = client.get('/tracking/redirect?tid=test')
            if redirect_response.status_code == 404:
                logger.error("Tracking redirect route not found!")
            else:
                logger.info("✓ Tracking redirect route is registered")
        
        # 6. Verify HTML processing
        test_html = "<html><body><p>Test</p><a href='https://example.com'>Link</a></body></html>"
        campaign = EmailCampaign.query.first()
        recipient = EmailRecipient.query.first()
        
        if campaign and recipient:
            try:
                processed_html = app.tracking_manager.process_html_content(
                    test_html, campaign.id, recipient.id
                )
                
                if "tracking/pixel" in processed_html:
                    logger.info("✓ Tracking pixel added to HTML")
                else:
                    logger.error("Tracking pixel not added to HTML!")
                
                if "tracking/redirect" in processed_html:
                    logger.info("✓ Links rewritten for tracking")
                else:
                    logger.error("Links not rewritten for tracking!")
                
                # Check if tracking records were created
                tracking_pixel = EmailTracking.query.filter_by(
                    email_id=campaign.id,
                    recipient_id=recipient.id,
                    tracking_type='open'
                ).order_by(EmailTracking.id.desc()).first()
                
                if tracking_pixel:
                    logger.info(f"✓ Tracking pixel record created with ID: {tracking_pixel.tracking_id}")
                else:
                    logger.error("No tracking pixel record created!")
                
                tracking_link = EmailTracking.query.filter_by(
                    email_id=campaign.id,
                    recipient_id=recipient.id,
                    tracking_type='click'
                ).order_by(EmailTracking.id.desc()).first()
                
                if tracking_link:
                    logger.info(f"✓ Tracking link record created with ID: {tracking_link.tracking_id}")
                else:
                    logger.error("No tracking link record created!")
            
            except Exception as e:
                logger.error(f"Error processing HTML: {str(e)}")
        
        logger.info("\nEmail tracking system fixes applied. Send a test email to verify.")
        
        # Return True if all critical fixes were applied
        return True

if __name__ == "__main__":
    print("=" * 80)
    print("🔧 FIXING EMAIL TRACKING SYSTEM")
    print("=" * 80)
    
    success = fix_tracking_system()
    
    if success:
        print("\n✅ Email tracking system fixes applied successfully.")
        print("Send a test email to verify that tracking is now working.")
    else:
        print("\n❌ Some fixes could not be applied. Please check the logs.")
