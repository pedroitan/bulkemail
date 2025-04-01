"""
SQS Debug Tool

This script helps diagnose issues with your SQS queue and connection.
It checks:
1. If AWS credentials are properly configured
2. If the SQS queue exists and is accessible
3. If messages can be sent to and received from the queue

Usage:
python debug_sqs.py
"""

import os
import boto3
import json
import uuid
import time
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Colors for better readability
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_status(message, status, details=None):
    """Print status message with color"""
    status_colors = {
        "OK": Colors.GREEN,
        "WARNING": Colors.YELLOW,
        "ERROR": Colors.RED,
        "INFO": Colors.BLUE
    }
    
    color = status_colors.get(status, Colors.END)
    
    print(f"{message}... {color}{status}{Colors.END}")
    if details:
        print(f"    {Colors.BLUE}→ {details}{Colors.END}")

def check_aws_credentials():
    """Check if AWS credentials are set and valid"""
    aws_access_key = os.environ.get('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
    aws_region = os.environ.get('AWS_REGION')
    
    if not aws_access_key or not aws_secret_key:
        print_status("AWS credentials", "ERROR", "AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY not found in environment variables")
        return False
    
    if not aws_region:
        print_status("AWS region", "ERROR", "AWS_REGION not found in environment variables")
        return False
    
    print_status("AWS credentials", "OK", f"Using region: {aws_region}")
    return True

def check_sqs_queue():
    """Check if SQS queue exists and is accessible"""
    sqs_queue_url = os.environ.get('SQS_QUEUE_URL')
    sqs_queue_name = os.environ.get('SQS_QUEUE_NAME')
    sqs_region = os.environ.get('SQS_REGION') or os.environ.get('AWS_REGION')
    
    if not sqs_queue_url and not sqs_queue_name:
        print_status("SQS queue configuration", "ERROR", "Neither SQS_QUEUE_URL nor SQS_QUEUE_NAME found in environment variables")
        return None
    
    try:
        # Create SQS client
        sqs = boto3.client('sqs', region_name=sqs_region)
        
        if sqs_queue_url:
            # Try to get queue attributes to confirm it exists
            sqs.get_queue_attributes(
                QueueUrl=sqs_queue_url,
                AttributeNames=['QueueArn']
            )
            print_status("SQS queue access", "OK", f"Queue URL: {sqs_queue_url}")
            return sqs_queue_url
        else:
            # Get queue URL from name
            response = sqs.get_queue_url(QueueName=sqs_queue_name)
            queue_url = response['QueueUrl']
            print_status("SQS queue access", "OK", f"Found queue: {queue_url}")
            return queue_url
    
    except Exception as e:
        print_status("SQS queue access", "ERROR", f"Error: {str(e)}")
        return None

def test_message_send_receive(queue_url):
    """Test sending and receiving messages from the queue"""
    if not queue_url:
        return False
    
    sqs_region = os.environ.get('SQS_REGION') or os.environ.get('AWS_REGION')
    sqs = boto3.client('sqs', region_name=sqs_region)
    
    # Create a test message
    test_id = str(uuid.uuid4())
    test_message = {
        "Type": "Notification",
        "MessageId": f"test-{test_id}",
        "Message": json.dumps({
            "notificationType": "Delivery",
            "mail": {
                "timestamp": datetime.now().isoformat(),
                "messageId": f"test-message-{test_id}",
                "destination": ["test@example.com"]
            },
            "delivery": {
                "timestamp": datetime.now().isoformat(),
                "recipients": ["test@example.com"]
            }
        })
    }
    
    try:
        # Send message
        response = sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(test_message)
        )
        
        message_id = response.get('MessageId')
        if not message_id:
            print_status("SQS message send", "ERROR", "No MessageId returned")
            return False
        
        print_status("SQS message send", "OK", f"Message ID: {message_id}")
        
        # Wait for 2 seconds to allow the message to be available
        print_status("Waiting for message to be available", "INFO")
        time.sleep(2)
        
        # Receive message
        response = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=5,
            VisibilityTimeout=30
        )
        
        messages = response.get('Messages', [])
        if not messages:
            print_status("SQS message receive", "WARNING", "No message received (queue might be processing messages too quickly)")
            return True
        
        receipt_handle = messages[0].get('ReceiptHandle')
        
        # Delete the message to clean up
        sqs.delete_message(
            QueueUrl=queue_url,
            ReceiptHandle=receipt_handle
        )
        
        print_status("SQS message receive and delete", "OK", "Successfully received and deleted test message")
        return True
    
    except Exception as e:
        print_status("SQS message test", "ERROR", f"Error: {str(e)}")
        return False

def check_rate_limiter_settings():
    """Check if rate limiter settings are properly configured for SQS processing"""
    try:
        with open('app.py', 'r') as file:
            content = file.read()
            
        if 'TokenBucketRateLimiter' not in content:
            print_status("Rate limiter", "WARNING", "TokenBucketRateLimiter not found in app.py")
            return False
        
        # Do a very simple check for rate limiter initialization
        if 'sns_rate_limiter = TokenBucketRateLimiter' in content:
            print_status("Rate limiter initialization", "OK", "Rate limiter is initialized in app.py")
            return True
        else:
            print_status("Rate limiter initialization", "WARNING", "Rate limiter initialization not found in app.py")
            return False
    except Exception as e:
        print_status("Rate limiter check", "ERROR", f"Error: {str(e)}")
        return False

def check_sqs_enabled():
    """Check if SQS is enabled in the application configuration"""
    sqs_enabled = os.environ.get('SQS_ENABLED', 'false').lower() == 'true'
    
    if sqs_enabled:
        print_status("SQS enabled flag", "OK", "SQS_ENABLED is set to true")
    else:
        print_status("SQS enabled flag", "WARNING", "SQS_ENABLED is not set to true - SQS processing will not run")
    
    return sqs_enabled

def main():
    """Main function for testing SQS configuration"""
    print(f"\n{Colors.BOLD}====== SQS DEBUG TOOL ======{Colors.END}\n")
    print(f"{Colors.BLUE}This tool will check your SQS configuration and perform basic tests.{Colors.END}\n")
    
    # Step 1: Check if SQS is enabled
    check_sqs_enabled()
    
    # Step 2: Check AWS credentials
    if not check_aws_credentials():
        print("\nAWS credentials check failed. Fix credentials before continuing.")
        return
    
    # Step 3: Check SQS queue
    queue_url = check_sqs_queue()
    if not queue_url:
        print("\nSQS queue check failed. Make sure your queue exists and is properly configured.")
        return
    
    # Step 4: Test message send and receive
    test_message_send_receive(queue_url)
    
    # Step 5: Check rate limiter settings (important for handling large volumes of notifications)
    check_rate_limiter_settings()
    
    print(f"\n{Colors.BOLD}====== END OF SQS DEBUG ======{Colors.END}\n")
    print(f"{Colors.BLUE}If all checks passed, your SQS configuration should be working correctly.{Colors.END}")
    print(f"{Colors.BLUE}If there were any warnings or errors, review the messages above and fix the issues.{Colors.END}")

if __name__ == "__main__":
    main()
