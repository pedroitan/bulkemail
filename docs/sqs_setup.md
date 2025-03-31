# Setting Up SQS for SNS Notifications

This guide explains how to set up Amazon SQS to handle SNS notifications from your email campaigns, especially for large campaigns with up to 40,000 recipients. This approach solves the problem of Render's free tier services being overwhelmed by too many simultaneous SNS notifications.

## Benefits of Using SQS for SNS Notifications

1. **No Data Loss**: Preserves all notifications instead of dropping them with aggressive filtering
2. **Controlled Processing**: Process notifications at a rate Render's free tier can handle
3. **Better Analytics**: Retain all email events including opens, clicks, and deliveries
4. **Server Stability**: Prevents 502 Bad Gateway errors during large campaigns (especially when sending 3,000+ emails)
5. **Complementary to Rate Limiter**: Works alongside the token bucket rate limiter to provide multiple layers of protection
6. **Compatible with Synchronous Processing**: Designed to work with the synchronous email sending process on Render's free tier

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

### Step 3: Add Required IAM Permissions

1. Navigate to the IAM service in AWS Management Console
2. Go to the "Policies" section and click "Create Policy"
3. Switch to the JSON editor and enter the following policy (replace with your actual values):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sqs:SendMessage",
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes",
        "sqs:GetQueueUrl"
      ],
      "Resource": "arn:aws:sqs:REGION:ACCOUNT_ID:QUEUE_NAME"
    }
  ]
}
```

Replace:
- `REGION` with your AWS region (e.g., `us-east-2`)
- `ACCOUNT_ID` with your AWS account ID
- `QUEUE_NAME` with the name of your SQS queue

4. Name your policy (e.g., "EmailBulkSQSPermissions") and create it
5. Go to the "Users" section, select your user
6. Click "Add permissions" and attach your newly created policy

### Step 4: Subscribe the SQS Queue to the SNS Topic

1. Navigate to the SNS service in AWS Management Console
2. Select your topic for SES notifications
3. Click "Create subscription"
4. For "Protocol", select "Amazon SQS"
5. For "Endpoint", select the ARN of your SQS queue
6. Leave other settings at default values
7. Click "Create subscription"

### Step 5: Configure the Application

1. Update your application's environment variables:

```
SQS_ENABLED=true
SQS_QUEUE_URL=https://sqs.REGION.amazonaws.com/ACCOUNT_ID/QUEUE_NAME
SQS_REGION=REGION  # Make sure this matches your SQS queue region

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

2. **Multi-layered Protection System**:
   - **Layer 1 - SNS Direct Processing**: When `SNS_DIRECT_DISABLED=true`, incoming SNS webhooks return 200 OK immediately without processing
   - **Layer 2 - Token Bucket Rate Limiter**: For direct processing, the rate limiter ensures only critical notifications (bounces, complaints) are processed immediately
   - **Layer 3 - SQS Queue**: All notifications are stored in SQS for later processing at a controlled rate

3. **Processing Rate Control**:
   - Messages are processed in batches of 10 every minute
   - Small delays (0.5 seconds) between processing each message
   - Graceful error handling with automatic retries (messages stay in queue if processing fails)

4. **Implementation Details**:
   - A scheduled job runs every minute to process SQS messages
   - The job runs as a module-level function to avoid APScheduler serialization issues
   - Messages are automatically deleted after successful processing
   - Works alongside the synchronous email processing implemented for Render's free tier

## Testing the Setup

1. **Verify Queue Connection**:
   - Visit `/api/process-sqs-queue` in your application
   - Should return a response indicating the queue is being processed

2. **Send a Test Campaign**:
   - Send a small test email campaign
   - Check your logs for "Forwarded SNS notification to SQS queue" messages
   - Monitor the processing of these messages in subsequent log entries

## Troubleshooting

1. **No Messages Being Processed or Access Denied Errors**:
   - Check your `SQS_ENABLED`, `SQS_QUEUE_URL`, and `SQS_REGION` environment variables
   - Verify SNS subscription status (should be "Confirmed")
   - Check SQS queue access policy
   - Ensure the APScheduler is running (check logs for "Scheduler initialized and running: True")
   - **IAM Permissions**: Verify your IAM user has the required permissions (sqs:ReceiveMessage, sqs:DeleteMessage, etc.)
   - **Region Mismatch**: Ensure your `SQS_REGION` matches the region where your queue is created

2. **Permission Issues**:
   - Ensure your AWS credentials have permissions for SQS operations
   - Check CloudWatch logs for specific error messages

3. **Rate Limiting Still Occurring**:
   - Set `SQS_ENABLED=true` and `SNS_DIRECT_DISABLED=true` to route all processing through SQS
   - Verify the token bucket rate limiter configuration
   - Check if the scheduled job is running (logs should show "Processing X SQS messages from scheduled job")

4. **Job Scheduling Issues**:
   - If you encounter APScheduler serialization errors, ensure you're using the module-level approach
   - Check if local/module imports in sqs_jobs.py are causing circular dependencies

## Optimizing for Render's Free Tier

This SQS setup works in conjunction with two other optimizations:

1. **Synchronous Email Processing**: Campaigns are processed synchronously instead of using background workers
2. **Token Bucket Rate Limiter**: Prioritizes critical notifications while limiting less important ones

Together, these three systems provide a robust solution for sending large email campaigns (up to 40,000 emails) on Render's free tier without encountering 502 errors or getting campaigns stuck in "pending" status.
