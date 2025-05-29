#!/usr/bin/env python
"""
Comprehensive diagnostic for email tracking system.
This script will test each component of the tracking system.
"""

import os
import sys
import logging
import json
import re
from datetime import datetime, timedelta
import requests
from urllib.parse import urlparse

# Set up environment
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
os.environ["FLASK_ENV"] = "development"

# Import Flask app and models
from app import app, db
from models import EmailCampaign, EmailRecipient, EmailTracking, EmailTrackingEvent

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TrackingDiagnostic:
    def __init__(self):
        self.issues_found = []
        self.successes = []
        self.app_context = app.app_context()
        self.app_context.__enter__()  # Enter the app context
        
    def cleanup(self):
        """Clean up resources"""
        self.app_context.__exit__(None, None, None)  # Exit the app context
    
    def log_issue(self, component, message, severity="ERROR"):
        """Log an issue found during diagnostics"""
        issue = {
            "component": component,
            "message": message,
            "severity": severity
        }
        logger.error(f"[{severity}] {component}: {message}")
        self.issues_found.append(issue)
        
    def log_success(self, component, message):
        """Log a successful test"""
        success = {
            "component": component,
            "message": message
        }
        logger.info(f"[SUCCESS] {component}: {message}")
        self.successes.append(success)
    
    def check_email_service_setup(self):
        """Check if the email service is properly set up"""
        try:
            email_service = app.get_email_service()
            if not email_service:
                self.log_issue("Email Service", "Email service is not initialized")
                return False
                
            # Check if tracking is enabled
            if not hasattr(email_service, 'tracking_enabled') or not email_service.tracking_enabled:
                self.log_issue("Email Service", "Tracking is not enabled in the email service")
                return False
                
            # Check if tracking manager is attached
            if not hasattr(email_service, 'tracking_manager') or not email_service.tracking_manager:
                self.log_issue("Email Service", "Tracking manager is not attached to email service")
                return False
                
            # Verify tracking domain
            if not email_service.tracking_manager.tracking_domain:
                self.log_issue("Tracking Manager", "Tracking domain is not set")
                return False
                
            self.log_success("Email Service", "Email service is properly set up with tracking enabled")
            return True
        except Exception as e:
            self.log_issue("Email Service", f"Error checking email service: {str(e)}")
            return False
    
    def check_tracking_routes(self):
        """Check if tracking routes are properly defined"""
        try:
            # Check if tracking pixel route exists
            tracking_routes = [rule for rule in app.url_map.iter_rules() 
                              if 'tracking/pixel' in str(rule)]
                              
            if not tracking_routes:
                self.log_issue("Tracking Routes", "Tracking pixel route is not defined")
                return False
                
            # Check if tracking link route exists
            link_routes = [rule for rule in app.url_map.iter_rules() 
                          if 'tracking/link' in str(rule)]
                          
            if not link_routes:
                self.log_issue("Tracking Routes", "Tracking link route is not defined")
                return False
                
            self.log_success("Tracking Routes", f"Tracking routes are properly defined: {[str(r) for r in tracking_routes + link_routes]}")
            return True
        except Exception as e:
            self.log_issue("Tracking Routes", f"Error checking tracking routes: {str(e)}")
            return False
    
    def check_tracking_database(self):
        """Check if tracking database tables exist and have proper structure"""
        try:
            # Check if EmailTracking table exists
            tracking_count = EmailTracking.query.count()
            logger.info(f"Found {tracking_count} tracking records")
            
            # Check if EmailTrackingEvent table exists
            event_count = EmailTrackingEvent.query.count()
            logger.info(f"Found {event_count} tracking events")
            
            # Check recipients with opens
            recipients_with_opens = EmailRecipient.query.filter(EmailRecipient.open_count > 0).count()
            logger.info(f"Found {recipients_with_opens} recipients with opens")
            
            self.log_success("Tracking Database", "Tracking database tables exist and contain data")
            return True
        except Exception as e:
            self.log_issue("Tracking Database", f"Error checking tracking database: {str(e)}")
            return False
    
    def check_html_processing(self):
        """Check if email HTML is processed correctly to include tracking pixel and rewrite links"""
        try:
            email_service = app.get_email_service()
            tracking_manager = email_service.tracking_manager
            
            # Create a test HTML
            test_html = """
            <html>
            <body>
                <p>Test email content</p>
                <a href="https://example.com">Test link</a>
            </body>
            </html>
            """
            
            # Create a test recipient for tracking
            campaign = EmailCampaign.query.first()
            if not campaign:
                self.log_issue("HTML Processing", "No campaign found for testing HTML processing")
                return False
                
            recipient = EmailRecipient.query.filter_by(campaign_id=campaign.id).first()
            if not recipient:
                self.log_issue("HTML Processing", "No recipient found for testing HTML processing")
                return False
            
            # Process the HTML
            processed_html = tracking_manager.process_html_for_tracking(
                html_content=test_html,
                email_id=campaign.id,
                recipient_id=recipient.id
            )
            
            # Check if tracking pixel is added
            if 'tracking/pixel' not in processed_html:
                self.log_issue("HTML Processing", "Tracking pixel not added to HTML")
                return False
                
            # Check if link is rewritten
            if 'tracking/link' not in processed_html or 'example.com' not in processed_html:
                self.log_issue("HTML Processing", "Links not rewritten in HTML")
                return False
                
            # Extract tracking IDs for verification
            pixel_match = re.search(r'tracking/pixel/([a-f0-9-]+)', processed_html)
            link_match = re.search(r'tracking/link/([a-f0-9-]+)', processed_html)
            
            if not pixel_match:
                self.log_issue("HTML Processing", "Could not extract tracking pixel ID")
                return False
                
            if not link_match:
                self.log_issue("HTML Processing", "Could not extract tracking link ID")
                return False
                
            pixel_id = pixel_match.group(1)
            link_id = link_match.group(1)
            
            # Verify tracking records exist in database
            pixel_record = EmailTracking.query.filter_by(tracking_id=pixel_id).first()
            if not pixel_record:
                self.log_issue("HTML Processing", f"Tracking record for pixel ID {pixel_id} not found in database")
                return False
                
            link_record = EmailTracking.query.filter_by(tracking_id=link_id).first()
            if not link_record:
                self.log_issue("HTML Processing", f"Tracking record for link ID {link_id} not found in database")
                return False
            
            self.log_success("HTML Processing", "Email HTML is processed correctly with tracking pixel and rewritten links")
            return True
        except Exception as e:
            self.log_issue("HTML Processing", f"Error checking HTML processing: {str(e)}")
            return False
    
    def check_tracking_endpoints(self):
        """Test if tracking endpoints can be accessed and record events"""
        try:
            # Find an existing tracking record
            tracking_record = EmailTracking.query.filter_by(tracking_type='open').first()
            if not tracking_record:
                self.log_issue("Tracking Endpoints", "No existing open tracking record found for testing endpoints")
                return False
            
            # Get the tracking domain
            email_service = app.get_email_service()
            tracking_domain = email_service.tracking_manager.tracking_domain
            
            # Create the tracking pixel URL
            tracking_url = f"{tracking_domain}/tracking/pixel/{tracking_record.tracking_id}.png"
            parsed_url = urlparse(tracking_url)
            
            logger.info(f"Testing tracking endpoint: {tracking_url}")
            logger.info(f"Parsed URL: scheme={parsed_url.scheme}, netloc={parsed_url.netloc}, path={parsed_url.path}")
            
            # Check if the URL is localhost or a public URL
            if parsed_url.netloc in ('localhost', '127.0.0.1') or parsed_url.netloc.startswith('localhost:'):
                logger.info("Using local testing for tracking URL")
                
                # Create a test client for local testing
                with app.test_client() as client:
                    # Determine the correct path
                    path = parsed_url.path
                    if parsed_url.query:
                        path = f"{path}?{parsed_url.query}"
                    
                    logger.info(f"Making request to path: {path}")
                    
                    # Make a request to the tracking endpoint
                    response = client.get(path)
                    logger.info(f"Response status: {response.status_code}")
                    
                    if response.status_code != 200:
                        self.log_issue("Tracking Endpoints", f"Tracking endpoint returned status {response.status_code}")
                        return False
            else:
                # It's a public URL, try to access it directly
                try:
                    logger.info(f"Making request to URL: {tracking_url}")
                    response = requests.get(tracking_url)
                    logger.info(f"Response status: {response.status_code}")
                    
                    if response.status_code != 200:
                        self.log_issue("Tracking Endpoints", f"Tracking endpoint returned status {response.status_code}")
                        return False
                except Exception as e:
                    self.log_issue("Tracking Endpoints", f"Error accessing tracking URL: {str(e)}")
                    return False
            
            # Check if a tracking event was created for this request
            events_before = EmailTrackingEvent.query.filter_by(tracking_id=tracking_record.tracking_id).count()
            
            # Wait a moment to allow the event to be recorded
            import time
            time.sleep(1)
            
            # Refresh the database session
            db.session.expire_all()
            
            # Check for new events
            events_after = EmailTrackingEvent.query.filter_by(tracking_id=tracking_record.tracking_id).count()
            
            if events_after <= events_before:
                self.log_issue("Tracking Endpoints", "Tracking event was not recorded after accessing endpoint")
                return False
            
            # Check if recipient open count was updated
            recipient = EmailRecipient.query.get(tracking_record.recipient_id)
            if not recipient:
                self.log_issue("Tracking Endpoints", "Could not find recipient for tracking record")
                return False
                
            if not recipient.open_count or recipient.open_count == 0:
                self.log_issue("Tracking Endpoints", "Recipient open count was not updated after tracking event")
                return False
            
            self.log_success("Tracking Endpoints", "Tracking endpoints are working and recording events")
            return True
        except Exception as e:
            self.log_issue("Tracking Endpoints", f"Error checking tracking endpoints: {str(e)}")
            return False
    
    def check_tracking_displays(self):
        """Check if the UI correctly displays tracking data"""
        try:
            # Find campaigns with opens
            campaign_with_opens = db.session.query(EmailCampaign)\
                .join(EmailRecipient, EmailCampaign.id == EmailRecipient.campaign_id)\
                .filter(EmailRecipient.open_count > 0)\
                .first()
                
            if not campaign_with_opens:
                self.log_issue("Tracking UI", "No campaign with opens found to test UI display")
                return False
            
            # Test the tracking report for this campaign
            with app.test_client() as client:
                # Test tracking campaigns list page
                response = client.get('/tracking')
                if response.status_code != 200:
                    self.log_issue("Tracking UI", f"Tracking page returned status {response.status_code}")
                    return False
                
                # Check if the page content includes open counts
                content = response.data.decode('utf-8')
                if "Opens" not in content:
                    self.log_issue("Tracking UI", "Tracking page does not show 'Opens' label")
                    return False
                
                # Test specific campaign tracking report
                response = client.get(f'/tracking/report/{campaign_with_opens.id}')
                if response.status_code != 200:
                    self.log_issue("Tracking UI", f"Campaign tracking report returned status {response.status_code}")
                    return False
                
                # Check if the page content includes open stats
                content = response.data.decode('utf-8')
                if "Opens:" not in content:
                    self.log_issue("Tracking UI", "Campaign tracking report does not show 'Opens:' statistic")
                    return False
            
            self.log_success("Tracking UI", "Tracking UI correctly displays tracking data")
            return True
        except Exception as e:
            self.log_issue("Tracking UI", f"Error checking tracking UI: {str(e)}")
            return False
    
    def run_diagnostics(self):
        """Run all diagnostic checks"""
        print("=" * 80)
        print("🔍 EMAIL TRACKING SYSTEM DIAGNOSTICS")
        print("=" * 80)
        
        all_checks_passed = True
        
        # Run each check
        checks = [
            ("Email Service Setup", self.check_email_service_setup),
            ("Tracking Routes", self.check_tracking_routes),
            ("Tracking Database", self.check_tracking_database),
            ("HTML Processing", self.check_html_processing),
            ("Tracking Endpoints", self.check_tracking_endpoints),
            ("Tracking UI", self.check_tracking_displays)
        ]
        
        for name, check_func in checks:
            print(f"\n## Checking {name}...")
            result = check_func()
            if not result:
                all_checks_passed = False
        
        # Print summary
        print("\n" + "=" * 80)
        print("📊 DIAGNOSTIC SUMMARY")
        print("=" * 80)
        
        if all_checks_passed:
            print("\n✅ All checks PASSED! The tracking system appears to be working correctly.")
        else:
            print("\n❌ Some checks FAILED! Please review the issues below:")
            
            for issue in self.issues_found:
                print(f"\n- [{issue['severity']}] {issue['component']}: {issue['message']}")
                
            print("\nSuccessful components:")
            for success in self.successes:
                print(f"- {success['component']}: {success['message']}")
            
            # Print recommendation
            print("\n📋 RECOMMENDATION:")
            if any(issue['component'] == 'Email Service' for issue in self.issues_found):
                print("- The email service setup has issues. Check if tracking_manager is properly connected to email_service.")
            if any(issue['component'] == 'Tracking Routes' for issue in self.issues_found):
                print("- Tracking routes are not properly defined. Check app.py for route definitions.")
            if any(issue['component'] == 'Tracking Database' for issue in self.issues_found):
                print("- Database issues detected. Check your models.py and make sure tables are created.")
            if any(issue['component'] == 'HTML Processing' for issue in self.issues_found):
                print("- HTML is not being processed correctly for tracking. Check email_tracking.py.")
            if any(issue['component'] == 'Tracking Endpoints' for issue in self.issues_found):
                print("- Tracking endpoints are not working. Check the routes and handlers in app.py.")
            if any(issue['component'] == 'Tracking UI' for issue in self.issues_found):
                print("- UI is not displaying tracking data correctly. Check templates/tracking_*.html files.")
        
        return all_checks_passed
        
    def __del__(self):
        """Destructor"""
        self.cleanup()

if __name__ == "__main__":
    diagnostic = TrackingDiagnostic()
    diagnostic.run_diagnostics()
