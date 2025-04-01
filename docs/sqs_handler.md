# SQS Message Handler Documentation

This document provides detailed information about the SQS message handling system in the Email Bulk Sending application.

## Overview

The SQS handler is a critical component that enables reliable processing of AWS SES email notifications (bounces, complaints, deliveries, etc.) through a queuing system that prevents server overload during large campaigns.

## Key Features

1. **Synchronous Processing Compatible with Render's Free Tier**:
   - Processes messages directly within the web request context
   - Eliminates need for separate background worker processes 
   - Works reliably on platforms that don't maintain background processes

2. **Controlled Rate Processing**:
   - Processes messages in small batches (10 by default)
   - Implements small delays between message processing
   - Properly manages message visibility to prevent duplicate processing

3. **Robust Error Handling**:
   - Messages that fail processing remain in the queue
   - Implements exponential backoff through SQS visibility timeout
   - Detailed logging for debugging notification issues

## Integration with Token Bucket Rate Limiter

The SQS handler works alongside the token bucket rate limiter to provide multiple layers of protection:

1. **Primary Layer**: SQS queuing with controlled batch processing
2. **Secondary Layer**: Token bucket rate limiter for direct notifications
3. **Tertiary Layer**: Selective processing of non-critical events during peak loads

The token bucket rate limiter specifically:
- Prioritizes critical notifications (bounces, complaints)
- Processes only 10 notifications per second
- Uses thread-safe implementation with proper locking
- Returns 200 OK for rate-limited requests to prevent AWS retries

## Code Structure and Flow

### Initialization and Configuration

```python
# Get SQS queue URL from environment variable
queue_url = os.getenv('SQS_QUEUE_URL')

# Create SQS client with AWS credentials
sqs = boto3.client('sqs', 
                  region_name=os.getenv('AWS_REGION', 'us-east-2'),
                  aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                  aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'))
```

### Message Receiving Process

1. Receive messages in batches with long polling:
```python
response = sqs.receive_message(
    QueueUrl=queue_url,
    MaxNumberOfMessages=max_messages,  # Default: 10
    WaitTimeSeconds=10,  # Long polling
    VisibilityTimeout=60  # 1 minute to process
)
```

2. Extract messages from response:
```python
messages = response.get('Messages', [])
```

3. Process each message:
```python
for message in messages:
    # Process message content
    # Delete after successful processing
```

### Message Processing Flow

1. Extract message body and receipt handle
2. Parse message body as JSON
3. Verify it's an SNS notification (Type = 'Notification')
4. Extract the notification data from the Message field
5. Determine notification type (Bounce, Complaint, Delivery, etc.)
6. Route to appropriate handler based on type
7. Delete message after successful processing

## Environment Configuration

The SQS handler is controlled by the following environment variables:

```
SQS_ENABLED=true             # Enable/disable SQS processing
SQS_QUEUE_URL=<url>          # URL of your SQS queue
SQS_MAX_MESSAGES=10          # Number of messages to process per batch
AWS_REGION=us-east-2         # AWS region for SQS queue
SNS_DIRECT_DISABLED=true     # When true, only process through SQS
```

## Notification Handler Types

The system includes handlers for all AWS SES notification types:

1. `handle_bounce_notification`: Processes email bounces, updates status, and marks permanent bounces
2. `handle_complaint_notification`: Processes spam complaints and prevents future sends
3. `handle_delivery_notification`: Confirms successful email delivery
4. `handle_delivery_delay_notification`: Tracks temporary delivery delays
5. `handle_send_notification`: Confirms email was sent (but not necessarily delivered)
6. `handle_open_notification`: Tracks when recipients open emails
7. `handle_click_notification`: Tracks when recipients click links in emails

## Logging and Debugging

The system implements comprehensive logging for tracking and debugging:

```python
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('sqs_jobs.log')
    ]
)
```

Key events that are logged:
- Message receipt with batch size information
- Message content for debugging
- Notification type and processing
- Success/failure status
- Database update confirmations
- Error details for troubleshooting

## Testing Tools

The application includes several testing tools for the SQS notification flow:

1. `test_sns_notification_handlers.py`: Tests direct notification handling
2. `test_sqs_notification_flow.py`: Tests the entire SNS → SQS flow
3. `debug_sqs_jobs.py`: Provides detailed debugging for SQS message processing
