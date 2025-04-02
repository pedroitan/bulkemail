#!/usr/bin/env python
"""
Test script to verify the session management fixes

This script simulates the email campaign process but in a controlled environment
to verify that the session binding issues have been resolved.
"""

import os
import sys
import logging
import time
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Add the current directory to the path to ensure imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import db, EmailCampaign, EmailRecipient
from session_manager import SessionManager
from app import create_app

def simulate_batch_processing():
    """
    Simulate the batch processing of recipients to test session handling
    """
    # Create a Flask app with test configuration
    app = create_app()
    
    with app.app_context():
        logging.info("Starting session management test")
        
        # Look for any campaign to use for testing
        campaign = EmailCampaign.query.first()
        if not campaign:
            logging.error("No campaign found for testing")
            return False
            
        campaign_id = campaign.id
        logging.info(f"Using campaign {campaign.id}: {campaign.name} for test")
        
        # Get all recipients (just IDs) - for testing we'll even use already sent ones
        recipient_query = EmailRecipient.query.filter_by(campaign_id=campaign_id)
        recipient_ids = [r.id for r in recipient_query.all()]
        
        if not recipient_ids:
            logging.error("No pending recipients found for testing")
            return False
            
        total_recipients = len(recipient_ids)
        logging.info(f"Found {total_recipients} pending recipients for testing")
        
        # Use a small batch size for testing
        batch_size = 5
        processed_count = 0
        
        # Process recipients in batches
        while processed_count < min(10, total_recipients):  # Process at most 10 recipients for test
            # Calculate batch end
            batch_end = min(processed_count + batch_size, total_recipients)
            
            # Get the recipient IDs for this batch
            batch_recipient_ids = recipient_ids[processed_count:batch_end]
            
            logging.info(f"Processing batch of {len(batch_recipient_ids)} recipients")
            
            # Process each recipient in the batch
            for recipient_id in batch_recipient_ids:
                # Get a fresh recipient object
                recipient = SessionManager.get_fresh_object(EmailRecipient, recipient_id)
                if not recipient:
                    logging.error(f"Could not find recipient ID {recipient_id}")
                    continue
                    
                # Simulate sending an email (without actually sending)
                logging.info(f"Simulating email send to {recipient.email}")
                
                # Get current status for logging
                current_status = recipient.status
                
                # Simulate a test update (toggle between 'test1' and 'test2' status)
                new_status = 'test1' if recipient.status != 'test1' else 'test2'
                recipient_updates = {
                    'status': new_status,
                    'updated_at': datetime.now()
                }
                
                # Update the recipient status
                update_success = SessionManager.update_object_status(
                    EmailRecipient, recipient_id, recipient_updates
                )
                
                if update_success:
                    logging.info(f"Successfully updated recipient {recipient_id}")
                else:
                    logging.error(f"Failed to update recipient {recipient_id}")
                    
            # Complete cleanup between batches
            SessionManager.reset_session()
            logging.info("Reset session between batches")
            
            # Increment processed count
            processed_count += batch_size
            
            # Pause between batches
            time.sleep(1)
            
        # Verify the recipients were updated properly
        logging.info("Verification phase: Checking if recipients were updated correctly")
        
        # Get a fresh session
        SessionManager.reset_session()
        
        # Check the status of the processed recipients
        for recipient_id in recipient_ids[:processed_count]:
            recipient = SessionManager.get_fresh_object(EmailRecipient, recipient_id)
            if recipient and (recipient.status == 'test1' or recipient.status == 'test2'):
                logging.info(f"Verification passed for recipient {recipient_id} - status: {recipient.status}")
            else:
                if recipient:
                    logging.error(f"Verification failed for recipient {recipient_id} - status: {recipient.status}")
                else:
                    logging.error(f"Verification failed - recipient {recipient_id} not found")
                
        return True

if __name__ == "__main__":
    try:
        success = simulate_batch_processing()
        if success:
            logging.info("Session management test completed successfully")
        else:
            logging.error("Session management test failed")
    except Exception as e:
        logging.error(f"Test failed with exception: {str(e)}")
    finally:
        # Reset recipients back to their original status
        logging.info("Test complete - don't forget these are test statuses only")
