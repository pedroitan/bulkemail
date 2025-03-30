"""
Email Sending Test Script

This script provides a simple way to test the email sending functionality
without involving the Flask application.
"""

import os
import sys
import logging
import boto3
from dotenv import load_dotenv, find_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_send_email(recipient_email):
    """Test sending an email to the specified recipient"""
    
    print(f"\n{'='*50}")
    print(f"TESTING EMAIL SENDING TO: {recipient_email}")
    print(f"{'='*50}\n")
    
    # Load environment variables
    load_dotenv(find_dotenv())
    
    # Get AWS credentials directly from environment
    aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
    aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
    aws_region = os.environ.get('AWS_REGION')
    sender_email = os.environ.get('SENDER_EMAIL')
    configuration_set = os.environ.get('SES_CONFIGURATION_SET')
    
    # Debug information
    print("AWS Credentials:")
    print(f"  - Access Key ID: {aws_access_key_id[:4]}{'*'*(len(aws_access_key_id)-8)}{aws_access_key_id[-4:]}")
    print(f"  - Secret Key: {'*'*10}")
    print(f"  - Region: {aws_region}")
    print(f"  - Sender Email: {sender_email}")
    print(f"  - Configuration Set: {configuration_set}")
    
    try:
        # Create SES client directly
        print("\nInitializing AWS SES client...")
        ses_client = boto3.client(
            'ses',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_region
        )
        
        # Set up test email content
        subject = "Test Email from Email Bulk Scheduler"
        body_html = """
        <html>
            <head></head>
            <body>
                <h1>Test Email</h1>
                <p>This is a test email sent from the Email Bulk Scheduler application.</p>
                <p>If you received this email, the email sending functionality is working correctly.</p>
            </body>
        </html>
        """
        body_text = "This is a test email sent from the Email Bulk Scheduler application."
        
        # Construct sender with name if available
        sender = f"Email Bulk Scheduler <{sender_email}>"
        
        # Prepare email parameters
        email_params = {
            'Source': sender,
            'Destination': {
                'ToAddresses': [recipient_email]
            },
            'Message': {
                'Subject': {
                    'Data': subject
                },
                'Body': {
                    'Html': {
                        'Data': body_html
                    },
                    'Text': {
                        'Data': body_text
                    }
                }
            }
        }
        
        # Add configuration set if available
        if configuration_set:
            print(f"NOTE: Using configuration set '{configuration_set}' might fail if it doesn't exist in AWS SES.")
            print(f"      To create it, go to AWS SES console and create a configuration set with this name.")
            print(f"      For testing, we'll try without the configuration set first.\n")
            
            # Try sending without the configuration set
            try:
                print("\nSending email without configuration set...")
                response = ses_client.send_email(**email_params)
                message_id = response.get('MessageId')
                
                print(f"\n✅ SUCCESS: Email sent successfully!")
                print(f"Message ID: {message_id}")
                return True
            except Exception as e:
                print(f"\nCouldn't send without configuration set: {str(e)}")
                print("Trying with configuration set as a last resort...")
                email_params['ConfigurationSetName'] = configuration_set
        
        # Send the email
        try:
            print("\nSending email...")
            response = ses_client.send_email(**email_params)
            message_id = response.get('MessageId')
            
            print(f"\n✅ SUCCESS: Email sent successfully!")
            print(f"Message ID: {message_id}")
            return True
        except Exception as e:
            if "ConfigurationSetDoesNotExist" in str(e):
                print(f"\n❌ ERROR: The configuration set '{configuration_set}' doesn't exist in AWS SES.")
                print("   Please create it in the AWS SES console or remove it from your .env file.")
                print("   You can set SES_CONFIGURATION_SET= (empty) in your .env file to disable it.")
            else:
                print(f"\n❌ ERROR: Failed to send email: {str(e)}")
            
            import traceback
            traceback.print_exc()
            return False
        
    except Exception as e:
        print(f"\n❌ ERROR: Failed to send email: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Check if an email address was provided
    if len(sys.argv) > 1:
        recipient = sys.argv[1]
    else:
        # Default to Amazon SES testing email
        recipient = "success@simulator.amazonses.com"
    
    # Run the test
    test_send_email(recipient)
