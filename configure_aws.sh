#!/bin/bash

# Load environment variables from .env file
set -a
source .env
set +a

# Configure AWS CLI using the loaded environment variables
aws configure set aws_access_key_id "$AWS_ACCESS_KEY_ID"
aws configure set aws_secret_access_key "$AWS_SECRET_ACCESS_KEY"
aws configure set region "${AWS_REGION:-us-east-2}"
aws configure set output json

echo "AWS CLI configured with credentials from .env file"

# Apply the SQS policy to allow SNS to send messages to SQS
aws sqs set-queue-attributes \
  --queue-url "$SQS_QUEUE_URL" \
  --attributes file://sqs_policy.json

echo "SQS policy applied to allow SNS to send notifications to your queue"

# Run the verification script to test the SES → SNS → SQS flow
echo "Running verification script to test notification flow..."
python verify_ses_sns_sqs.py
