#!/usr/bin/env python3
"""
Simple script to test if AWS credentials are valid
"""
import os
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def test_aws_credentials():
    """Test if AWS credentials are valid by making a simple API call"""
    # Get AWS credentials from environment variables
    aws_access_key = os.environ.get('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
    aws_region = os.environ.get('AWS_REGION', 'us-east-1')
    
    if not aws_access_key or not aws_secret_key:
        print("ERROR: AWS credentials not found in environment variables.")
        print("Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in your .env file.")
        return False
    
    print(f"Testing AWS credentials...")
    print(f"AWS Region: {aws_region}")
    print(f"Access Key ID: {aws_access_key[:5]}...{aws_access_key[-4:]}")
    
    try:
        # Try to create a simple AWS client (STS is a service that all IAM users can access)
        sts = boto3.client(
            'sts',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=aws_region
        )
        
        # Call GetCallerIdentity to verify the credentials
        response = sts.get_caller_identity()
        
        print("\n✅ AWS credentials are valid!")
        print(f"Account ID: {response['Account']}")
        print(f"User ARN: {response['Arn']}")
        print(f"User ID: {response['UserId']}")
        print("\nNOTE: While your credentials are valid, your IAM user may not have sufficient permissions for SES operations.")
        print("To use SES, ensure your IAM user has the following permissions:")
        print("- ses:GetSendQuota")
        print("- ses:ListIdentities")
        print("- ses:SendEmail")
        print("- ses:VerifyEmailIdentity")
        return True
    except ClientError as e:
        print(f"\n❌ ERROR: Invalid AWS credentials.")
        print(f"Error details: {str(e)}")
        return False

if __name__ == '__main__':
    test_aws_credentials()
