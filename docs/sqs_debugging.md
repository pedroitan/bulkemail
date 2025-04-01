# SQS Testing and Debugging Guide

This guide provides steps to test and debug your SQS integration for handling AWS SES notifications in the email bulk application.

## Prerequisites

Make sure you have:
1. AWS account with access to SQS and SES
2. SQS queue already created
3. AWS credentials configured

## 1. Environment Variables Setup

First, ensure all required environment variables are set in your `.env` file:

```bash
# AWS credentials
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-2  # Your AWS region

# SQS configuration
SQS_ENABLED=true
SQS_QUEUE_URL=https://sqs.us-east-2.amazonaws.com/123456789012/your-queue-name
SQS_QUEUE_NAME=your-queue-name  # Optional if you have the URL
SQS_REGION=us-east-2  # Optional if same as AWS_REGION
```

## 2. Run the SQS Debug Tool

The application includes a debug tool to test your SQS connection:

```bash
python debug_sqs.py
```

This will:
- Check if SQS is enabled
- Verify AWS credentials
- Test connection to your SQS queue
- Send and receive a test message
- Verify rate limiter configuration

## 3. Inspect Log Files

If you're experiencing issues with SQS processing, check the application logs:

```bash
grep -r "SQS" logs/app.log
```

Look for errors like:
- Connection errors
- Authentication failures
- Message parsing issues
- Rate limiting messages

## 4. Manual SQS Message Testing

You can manually send a test SQS message that mimics an SES notification:

```python
import boto3
import json
import time

sqs = boto3.client('sqs', region_name='us-east-2')
queue_url = 'your-queue-url'

# Create a test SES delivery notification
message = {
    "Type": "Notification",
    "MessageId": "test-message-id",
    "Message": json.dumps({
        "notificationType": "Delivery",
        "mail": {
            "timestamp": "2023-01-01T12:00:00.000Z",
            "messageId": "test-message-id",
            "destination": ["test@example.com"]
        },
        "delivery": {
            "timestamp": "2023-01-01T12:00:00.000Z",
            "recipients": ["test@example.com"]
        }
    })
}

# Send to SQS
response = sqs.send_message(
    QueueUrl=queue_url,
    MessageBody=json.dumps(message)
)

print(f"Message sent with ID: {response['MessageId']}")
```

## 5. Check Rate Limiter Behavior

Your application uses a token bucket rate limiter to prevent server overload during large campaigns. Verify it's working:

1. Monitor application logs during message processing
2. Look for log entries with rate limiting information
3. Ensure critical notifications (bounces, complaints) bypass rate limiting
4. Verify normal notifications are properly throttled

Example log patterns to look for:
```
INFO - Rate limiter: Consumed token for critical notification
INFO - Rate limiter: Rate limited non-critical notification
```

## 6. Test SQS in the Application

To verify SQS is working in your application:

1. Send a test email through your application
2. Wait for SES to deliver the notification to your SQS queue
3. Check the application logs for SQS processing messages
4. Verify the email status is updated in the database

## 7. Debug Common Issues

### Connection Issues
- Verify your AWS credentials have SQS access permissions
- Check your network connectivity to AWS services
- Ensure your SQS queue exists and is in the correct region

### Message Processing Issues
- Inspect the format of messages in your SQS queue
- Verify the application can parse the message format
- Check for JSON parsing errors in logs

### Rate Limiting Issues
- Adjust rate limiter parameters if messages are dropping
- Default setup: 3 tokens max with 0.3 refill rate
- Increase token limit if legitimate messages are being dropped

## 8. Monitoring SQS in Production

For production environments:
- Set up CloudWatch alarms on queue size
- Monitor for dead-letter queue messages
- Implement logging for SQS processing statistics

## Conclusion

A properly configured SQS integration is crucial for handling AWS SES feedback events, especially for large email campaigns where the volume of notifications can overwhelm the server. The token bucket rate limiter prevents 502 errors while ensuring critical notifications (like bounces) are processed promptly.

By following this guide, you should be able to diagnose and fix most common SQS integration issues in your email bulk application.
