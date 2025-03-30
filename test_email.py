#!/usr/bin/env python3
"""
Test script for sending emails through Amazon SES
Use this script to verify your AWS SES configuration is working correctly
"""
import os
import sys
import argparse
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Debug output to check environment variables
print("Environment variables loaded from .env:")
print(f"AWS_ACCESS_KEY_ID: {'SET' if os.environ.get('AWS_ACCESS_KEY_ID') else 'NOT FOUND'}")
print(f"AWS_SECRET_ACCESS_KEY: {'SET' if os.environ.get('AWS_SECRET_ACCESS_KEY') else 'NOT FOUND'}")
print(f"AWS_REGION: {os.environ.get('AWS_REGION', 'NOT FOUND')}")
print(f"SENDER_EMAIL: {os.environ.get('SENDER_EMAIL', 'NOT FOUND')}")
print()

def test_ses_credentials():
    """Test if AWS SES credentials are valid"""
    # Get AWS credentials from environment variables
    aws_access_key = os.environ.get('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
    aws_region = os.environ.get('AWS_REGION', 'us-east-1')
    
    if not aws_access_key or not aws_secret_key:
        print("ERROR: AWS credentials not found in environment variables.")
        print("Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in your .env file.")
        return False
    
    try:
        # Create SES client
        ses = boto3.client(
            'ses',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=aws_region
        )
        
        # Call a simple API to verify credentials
        response = ses.get_send_quota()
        
        print("AWS SES credentials are valid!")
        print(f"SES Send Quota: {response['Max24HourSend']} emails per 24 hour period")
        print(f"SES Send Rate: {response['MaxSendRate']} emails per second")
        print(f"SES Sent Last 24h: {response['SentLast24Hours']} emails")
        
        return True
    except ClientError as e:
        print(f"ERROR: Invalid AWS credentials. {str(e)}")
        return False

def send_test_email(recipient, subject=None, body_text=None, body_html=None):
    """Send a test email using Amazon SES"""
    # Get AWS credentials from environment variables
    aws_access_key = os.environ.get('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
    aws_region = os.environ.get('AWS_REGION', 'us-east-1')
    sender_email = os.environ.get('SENDER_EMAIL')
    
    # Fallback for sender email if not found in environment variables
    if not sender_email:
        sender_email = "vendo147@itantech.com.br"  # Hardcoded fallback
        print(f"Using fallback sender email: {sender_email}")
    
    # Default values
    if not subject:
        subject = "Amazon SES Test Email"
    if not body_text:
        body_text = "This is a test email sent using Amazon SES."
    if not body_html:
        body_html = f"""
        <html>
        <body>
            <h1>Amazon SES Test Email</h1>
            <p>This is a test email sent using Amazon SES.</p>
            <p>This email confirms that your Amazon SES configuration is working correctly with the Bulk Email Scheduler application.</p>
        </body>
        </html>
        """
    
    try:
        # Create SES client
        ses = boto3.client(
            'ses',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=aws_region
        )
        
        # Sending the email
        response = ses.send_email(
            Source=sender_email,
            Destination={
                'ToAddresses': [recipient]
            },
            Message={
                'Subject': {
                    'Data': subject,
                    'Charset': 'UTF-8'
                },
                'Body': {
                    'Text': {
                        'Data': body_text,
                        'Charset': 'UTF-8'
                    },
                    'Html': {
                        'Data': body_html,
                        'Charset': 'UTF-8'
                    }
                }
            }
        )
        
        print(f"Email sent! Message ID: {response['MessageId']}")
        return True
    except ClientError as e:
        print(f"ERROR: Failed to send email. {str(e)}")
        
        # Check if it's a verification error
        if "Email address is not verified" in str(e):
            print("\nIMPORTANT: The sender email address must be verified in Amazon SES.")
            print(f"Please go to the AWS Management Console and verify: {sender_email}")
            
            # Check if in sandbox mode
            try:
                account_status = ses.get_account_sending_enabled()
                if account_status.get('Enabled', False) == False:
                    print("\nYour AWS account is still in SES sandbox mode.")
                    print("In sandbox mode, you can only send emails to verified addresses.")
                    print("Please also verify the recipient email address or request production access.")
            except:
                pass
        return False

def list_verified_emails():
    """List all verified email addresses"""
    # Get AWS credentials from environment variables
    aws_access_key = os.environ.get('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
    aws_region = os.environ.get('AWS_REGION', 'us-east-1')
    
    try:
        # Create SES client
        ses = boto3.client(
            'ses',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=aws_region
        )
        
        # Get verified email addresses
        response = ses.list_identities(
            IdentityType='EmailAddress'
        )
        
        if not response.get('Identities'):
            print("No verified email addresses found.")
            return
        
        print("\nVerified Email Addresses:")
        for identity in response.get('Identities', []):
            verification = ses.get_identity_verification_attributes(
                Identities=[identity]
            )
            status = verification.get('VerificationAttributes', {}).get(identity, {}).get('VerificationStatus', 'Unknown')
            print(f"  - {identity} ({status})")
        
        print("\nNOTE: In SES sandbox mode, you can only send FROM and TO verified addresses.")
        print("      To send to any address, request production access in the AWS SES Console.")
    except ClientError as e:
        print(f"ERROR: Failed to list verified emails. {str(e)}")

def verify_email(email):
    """Request verification for a new email address"""
    # Get AWS credentials from environment variables
    aws_access_key = os.environ.get('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
    aws_region = os.environ.get('AWS_REGION', 'us-east-1')
    
    try:
        # Create SES client
        ses = boto3.client(
            'ses',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=aws_region
        )
        
        # Request verification
        response = ses.verify_email_identity(
            EmailAddress=email
        )
        
        print(f"\nVerification email sent to {email}!")
        print("Please check the email inbox and click the verification link.")
        return True
    except ClientError as e:
        print(f"ERROR: Failed to request verification. {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Test Amazon SES functionality')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Verify SES credentials
    verify_parser = subparsers.add_parser('verify-credentials', help='Verify AWS SES credentials')
    verify_parser.set_defaults(func=lambda args: test_ses_credentials())
    
    # Send test email
    send_parser = subparsers.add_parser('send', help='Send a test email')
    send_parser.add_argument('recipient', help='Recipient email address')
    send_parser.add_argument('--subject', help='Email subject')
    send_parser.add_argument('--text', help='Email plain text body')
    send_parser.add_argument('--html', help='Email HTML body')
    send_parser.set_defaults(func=lambda args: send_test_email(
        args.recipient, args.subject, args.text, args.html
    ))
    
    # List verified emails
    list_parser = subparsers.add_parser('list-verified', help='List verified email addresses')
    list_parser.set_defaults(func=lambda args: list_verified_emails())
    
    # Verify new email
    verify_email_parser = subparsers.add_parser('verify-email', help='Request verification for a new email address')
    verify_email_parser.add_argument('email', help='Email address to verify')
    verify_email_parser.set_defaults(func=lambda args: verify_email(args.email))
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        # If no command is provided, verify credentials by default
        test_ses_credentials()
        list_verified_emails()
        print("\nTo send a test email:")
        print(f"python {sys.argv[0]} send your-email@example.com")
        print("\nTo verify a new email address:")
        print(f"python {sys.argv[0]} verify-email your-email@example.com")
        return
    
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
