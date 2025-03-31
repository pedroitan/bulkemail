# Setting Up SQS for SNS Notifications

This guide explains how to set up Amazon SQS to handle SNS notifications from your email campaigns, especially for large campaigns with up to 40,000 recipients. This approach solves the problem of Render's free tier services being overwhelmed by too many simultaneous SNS notifications.

## Benefits of Using SQS for SNS Notifications

1. **No Data Loss**: Preserves all notifications instead of dropping 99.5% of them with aggressive filtering
2. **Controlled Processing**: Process notifications at a rate Render's free tier can handle
3. **Better Analytics**: Retain all email events including opens, clicks, and deliveries
4. **Server Stability**: Prevents 502 Bad Gateway errors during large campaigns
5. **Simplified Architecture**: Reduces the complexity of rate limiting logic

## AWS Setup Instructions

### Step 1: Create an SQS Queue

1. Log in to your AWS Management Console
2. Navigate to the SQS service
3. Click "Create Queue"
4. Choose "Standard Queue" (not FIFO)
5. Enter a name for your queue (e.g., `email-bulk-notifications`)
6. Set the following basic settings:
   - Visibility timeout: 60 seconds
   - Message retention period: 4 days
   - Maximum message size: 256 KB
   - Delivery delay: 0 seconds
7. Leave other settings at default values
8. Click "Create Queue"

### Step 2: Set Up Queue Permissions for SNS

1. Select your newly created queue
2. Click the "Access policy" tab
3. Click "Edit"
4. Add or replace the policy with the following (replace placeholders with your actual values):

```json
{
  "Version": "2012-10-17",
  "Id": "sns-sqs-policy",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "sns.amazonaws.com"
      },
      "Action": "sqs:SendMessage",
      "Resource": "arn:aws:sqs:REGION:ACCOUNT_ID:QUEUE_NAME",
      "Condition": {
        "ArnEquals": {
          "aws:SourceArn": "arn:aws:sns:REGION:ACCOUNT_ID:SNS_TOPIC_NAME"
        }
      }
    }
  ]
}
```

Replace:
- `REGION` with your AWS region (e.g., `us-east-1`)
- `ACCOUNT_ID` with your AWS account ID
- `QUEUE_NAME` with the name of your SQS queue
- `SNS_TOPIC_NAME` with the name of your SNS topic

5. Click "Save"

### Step 3: Subscribe the SQS Queue to the SNS Topic

1. Navigate to the SNS service in AWS Management Console
2. Select your topic for SES notifications
3. Click "Create subscription"
4. For "Protocol", select "Amazon SQS"
5. For "Endpoint", select the ARN of your SQS queue
6. Leave other settings at default values
7. Click "Create subscription"

### Step 4: Configure the Application

1. Update your application's environment variables:

```
SQS_ENABLED=true
SQS_QUEUE_URL=https://sqs.REGION.amazonaws.com/ACCOUNT_ID/QUEUE_NAME

# Optionally disable direct SNS processing (recommended for Render free tier)
SNS_DIRECT_DISABLED=true
```

Replace:
- `REGION` with your AWS region
- `ACCOUNT_ID` with your AWS account ID
- `QUEUE_NAME` with your SQS queue name

2. Restart your application

## How It Works

1. **SNS Messages Flow**:
   - SES sends notifications to your SNS topic
   - SNS forwards these messages to your SQS queue
   - Your application processes messages from the queue at a controlled rate

2. **Processing Rate Control**:
   - Messages are processed in batches of 10 every minute
   - Critical notifications (bounces, complaints) are still processed immediately
   - Non-critical notifications (deliveries, opens, clicks) are processed from the queue

3. **Implementation Details**:
   - A scheduled job runs every minute to process SQS messages
   - The `/api/process-sqs-queue` endpoint can also be manually triggered
   - Messages are automatically deleted after successful processing

## Testing the Setup

1. **Verify Queue Connection**:
   - Visit `/api/process-sqs-queue` in your application
   - Should return a response indicating the queue is being processed

2. **Send a Test Campaign**:
   - Send a small test email campaign
   - Check your logs for "Forwarded SNS notification to SQS queue" messages
   - Monitor the processing of these messages in subsequent log entries

## Troubleshooting

1. **No Messages Being Processed**:
   - Check your `SQS_ENABLED` and `SQS_QUEUE_URL` environment variables
   - Verify SNS subscription status (should be "Confirmed")
   - Check SQS queue access policy

2. **Permission Issues**:
   - Ensure your AWS credentials have permissions for SQS operations
   - Check CloudWatch logs for specific error messages

3. **Rate Limiting Still Occurring**:
   - Set `SQS_ENABLED=true` to disable aggressive filtering
   - Check scheduler is running properly

This setup will significantly improve your application's ability to handle large email campaigns and prevent 502 errors on Render's free tier.
