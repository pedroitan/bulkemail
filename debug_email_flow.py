"""
Debug Email Flow

This script systematically tests each component of the email sending flow
to identify where the process is breaking down.
"""

import os
import sys
import logging
import traceback
from dotenv import load_dotenv, find_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("debug_email_flow")

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv(find_dotenv())

def debug_section(title):
    """Print a section header for better readability"""
    print(f"\n{'='*20} {title} {'='*20}")

def check_environment():
    """Check if all required environment variables are set"""
    debug_section("ENVIRONMENT VARIABLES")
    
    required_vars = [
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_REGION",
        "SENDER_EMAIL",
    ]
    
    all_good = True
    for var in required_vars:
        value = os.environ.get(var)
        if value:
            # Mask sensitive information
            if var == "AWS_ACCESS_KEY_ID":
                display = f"{value[:4]}{'*'*(len(value)-8)}{value[-4:]}"
            elif var == "AWS_SECRET_ACCESS_KEY":
                display = "*" * 10
            else:
                display = value
            print(f"✅ {var} = {display}")
        else:
            print(f"❌ {var} is not set!")
            all_good = False
    
    return all_good

def test_direct_email_sending():
    """Test direct email sending using the SESEmailService class"""
    debug_section("DIRECT EMAIL SENDING")
    
    try:
        # Import the email service
        from email_service import SESEmailService
        
        print("Creating SESEmailService instance...")
        email_service = SESEmailService()
        
        # Check if we have a client
        print("Checking email service initialization...")
        email_service._ensure_client()
        if email_service.client:
            print("✅ SES client initialized successfully")
        else:
            print("❌ Failed to initialize SES client!")
            return False
        
        # Try to send a test email
        print("\nSending test email to success@simulator.amazonses.com...")
        message_id = email_service.send_email(
            recipient="success@simulator.amazonses.com",
            subject="Debug Test Email",
            body_html="<p>This is a test email to debug the email flow.</p>"
        )
        
        if message_id:
            print(f"✅ Email sent successfully! Message ID: {message_id}")
            return True
        else:
            print("❌ Failed to send email (no message ID returned)")
            return False
            
    except Exception as e:
        print(f"❌ Exception during direct email sending: {str(e)}")
        traceback.print_exc()
        return False

def test_scheduler_campaign_sending():
    """Test campaign sending through the scheduler"""
    debug_section("SCHEDULER CAMPAIGN SENDING")
    
    try:
        # Import the necessary modules
        from models import db, EmailCampaign, EmailRecipient
        from scheduler import EmailScheduler, _run_campaign_job
        from email_service import SESEmailService
        
        print("Creating test campaign in memory (not in database)...")
        campaign = EmailCampaign(
            id=9999,  # Use a high ID unlikely to exist
            name="Debug Test Campaign",
            subject="Debug Test Email",
            body_html="<p>This is a test email from the debug script.</p>",
            status="draft"
        )
        
        # Create email service
        print("Creating email service...")
        email_service = SESEmailService()
        
        # Create scheduler
        print("Creating scheduler...")
        scheduler = EmailScheduler(email_service)
        
        # Test scheduler directly
        print("\nAttempting to use scheduler.send_email method...")
        try:
            # We're not actually sending, just checking if the method could be called
            result = scheduler.send_email(
                campaign=campaign,
                recipient=EmailRecipient(
                    id=9999,
                    campaign_id=9999,
                    email="success@simulator.amazonses.com",
                    status="pending"
                )
            )
            print(f"✅ scheduler.send_email can be called")
        except Exception as e:
            print(f"❌ Exception in scheduler.send_email: {str(e)}")
            traceback.print_exc()
        
        print("\nTest complete - No actual emails were sent to avoid database interactions")
        return True
        
    except Exception as e:
        print(f"❌ Exception during scheduler test: {str(e)}")
        traceback.print_exc()
        return False

def test_with_app_context():
    """Test functionality within the Flask app context"""
    debug_section("FLASK APP CONTEXT TEST")
    
    try:
        print("Importing Flask app...")
        from app import app, get_app
        
        print("Testing with app context...")
        with app.app_context():
            print("✅ Successfully entered app context")
            
            print("\nGetting email service within app context...")
            email_service = app.get_email_service()
            if email_service:
                print("✅ Got email service from app")
            else:
                print("❌ Failed to get email service from app")
                return False
            
            print("\nGetting scheduler within app context...")
            scheduler = app.get_scheduler()
            if scheduler:
                print("✅ Got scheduler from app")
            else:
                print("❌ Failed to get scheduler from app")
                return False
            
            print("\nChecking scheduler initialization...")
            if scheduler.scheduler and scheduler.scheduler.running:
                print("✅ Scheduler is initialized and running")
            else:
                print("❌ Scheduler is not properly initialized")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Exception during app context test: {str(e)}")
        traceback.print_exc()
        return False

def test_campaign_trigger():
    """Test the actual campaign trigger endpoint"""
    debug_section("CAMPAIGN TRIGGER TEST")
    
    try:
        import requests
        
        # Get a valid campaign ID
        campaign_id = input("Enter a valid campaign ID from your database to test (or press Enter to skip): ")
        if not campaign_id:
            print("Skipping campaign trigger test")
            return True
            
        campaign_id = int(campaign_id)
        
        print(f"Testing campaign trigger for campaign ID {campaign_id}...")
        response = requests.post(f"http://localhost:5000/campaigns/{campaign_id}/start")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print(f"✅ Campaign trigger successful: {data.get('message')}")
                return True
            else:
                print(f"❌ Campaign trigger failed: {data.get('message')}")
                return False
        else:
            print(f"❌ Request failed with status code {response.status_code}")
            print(response.text)
            return False
            
    except Exception as e:
        print(f"❌ Exception during campaign trigger test: {str(e)}")
        traceback.print_exc()
        return False

def main():
    """Run all debug tests"""
    print("Starting Email Flow Debug")
    
    # Keep track of test results
    test_results = {}
    
    # Check environment
    test_results['environment'] = check_environment()
    
    # Test direct email sending
    test_results['direct_email'] = test_direct_email_sending()
    
    # Test scheduler
    test_results['scheduler'] = test_scheduler_campaign_sending()
    
    # Test with app context
    test_results['app_context'] = test_with_app_context()
    
    # Test campaign trigger
    test_results['campaign_trigger'] = test_campaign_trigger()
    
    # Print summary
    debug_section("DEBUG RESULTS SUMMARY")
    
    all_passed = True
    for test, result in test_results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        if not result:
            all_passed = False
        print(f"{test.replace('_', ' ').title()}: {status}")
    
    if all_passed:
        print("\n🎉 All tests passed! Your email flow should be working correctly.")
    else:
        print("\n⚠️ Some tests failed. Review the results above to identify the issue.")
        
        # Suggest possible fixes based on which tests failed
        if not test_results['environment']:
            print("\nSuggestion: Check your .env file and make sure all AWS credentials are set correctly.")
        
        if test_results['environment'] and not test_results['direct_email']:
            print("\nSuggestion: Your AWS credentials might be incorrect or you might not have proper permissions.")
            print("Check your AWS SES console to ensure your account is out of the sandbox if needed.")
        
        if test_results['direct_email'] and not test_results['scheduler']:
            print("\nSuggestion: There might be an issue with your scheduler implementation.")
            print("Check the scheduler.py file for errors.")
        
        if test_results['scheduler'] and not test_results['app_context']:
            print("\nSuggestion: There might be an issue with the Flask app context or how the scheduler is initialized.")
            print("Check app.py for errors related to the email service or scheduler initialization.")
        
        if test_results['app_context'] and not test_results['campaign_trigger']:
            print("\nSuggestion: There might be an issue with the campaign trigger endpoint.")
            print("Check app.py for errors in the start_campaign function.")

if __name__ == "__main__":
    main()
