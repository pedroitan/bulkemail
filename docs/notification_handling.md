# Email Notification Handling System

This document explains the comprehensive notification handling system implemented in the Email Bulk Sending application. The system processes AWS SES email delivery events (bounces, complaints, delivery confirmations, etc.) through a robust SNS-SQS flow.

## System Architecture

The application uses a multi-layer approach to handle email delivery notifications:

```
AWS SES → SNS → SQS → Application Processor → Database
```

1. **AWS SES**: Sends emails and generates notifications for various delivery events
2. **SNS**: Receives notifications from SES and forwards them to subscribed endpoints
3. **SQS**: Queues notifications for asynchronous processing to prevent server overload
4. **Application Processor**: Processes queued messages at a controlled rate
5. **Database**: Updates recipient records with current delivery status

## Notification Types Handled

The system processes the following notification types from AWS SES:

| Event Type     | Description                                         | Database Update                           |
|----------------|-----------------------------------------------------|-------------------------------------------|
| Send           | Email was successfully sent to recipient's server    | Updates status to 'sent'                  |
| Delivery       | Email was successfully delivered to recipient        | Updates status to 'delivered'             |
| Bounce         | Email bounced back as undeliverable                  | Updates status to 'bounced'               |
| Complaint      | Recipient marked the email as spam                   | Updates status to 'complained'            |
| DeliveryDelay  | Delivery was delayed due to temporary issues         | Updates status to 'delayed'               |
| Open           | Recipient opened the email                           | Updates status to 'opened'                |
| Click          | Recipient clicked a link in the email                | Updates status to 'clicked'               |

## Rate Limiting Strategy

To prevent server overload during large campaigns (3,000+ emails), the system implements:

1. **Token Bucket Rate Limiter**: Limits direct SNS notifications to 10 per second
   - Uses a thread-safe implementation with proper locking
   - Maintains a token bucket with configurable capacity and refill rate
   - Critical notifications (bounces, complaints) bypass rate limiting
   - Returns 200 OK for rate-limited requests to prevent AWS retries

2. **SQS-Based Processing**: Processes notifications asynchronously at a controlled rate
   - Queues all notifications for uniform handling
   - Processes in small batches (default 10 messages) with controlled timing
   - Maintains message visibility timeout to prevent duplicate processing

3. **Multi-Layer Protection**:
   - Primary defense: SQS queuing with controlled processing rate
   - Secondary defense: Token bucket rate limiter for direct notifications
   - Tertiary defense: Sampling of non-critical events during peak loads

This approach prevents the 502 Bad Gateway errors that previously occurred during large campaigns when the application was overwhelmed by too many simultaneous notifications.

## Implementation Details

### SNS Notification Handler (`app.py`)

- Receives webhook notifications from AWS SNS
- Forwards notifications to SQS for asynchronous processing
- When SNS_DIRECT_DISABLED is true, the system processes notifications only through SQS
- Implements handlers for all notification types (Bounce, Complaint, Delivery, DeliveryDelay, Send, Open, Click)
- Uses token bucket rate limiting for direct webhook calls
- Returns 200 OK status even for rate-limited requests to prevent AWS retries

### SQS Message Processor (`sqs_jobs.py`)

- Designed for synchronous processing compatible with Render's free tier
- Runs within the web request context without requiring separate worker processes
- Retrieves messages from SQS queue in controlled batches
- Parses SNS message format to extract notification data
- Routes notifications to appropriate handlers based on type
- Updates database with new delivery status information
- Properly manages Flask application context to avoid serialization issues

### Synchronous Processing Approach

The application uses a synchronous approach for both email sending and notification processing:

- Email campaigns are processed within the web request context
- Notifications are queued in SQS and processed in controlled batches
- This approach eliminates the need for long-running background workers
- Compatible with hosting platforms like Render's free tier that don't maintain background processes

### Database Status Updates

When notifications are processed, recipient records are updated with:
- Current delivery status
- Timestamp of the event
- Additional diagnostic information (for bounces)
- Global status flags for permanent issues (to prevent sending to problematic emails in future campaigns)

## Testing and Verification

The following tools are available to test the notification flow:

1. `test_sns_notification_handlers.py`: Tests direct notification delivery to app endpoint
2. `test_sqs_notification_flow.py`: Tests sending notifications through SQS and processing them
3. `debug_sqs_jobs.py`: Enhanced debugging tool for SQS message processing
4. `verify_sns_sqs_flow.py`: Verifies the entire flow from SES to SNS to SQS to application

## Configuration

Key environment variables that control notification handling:

```
SNS_DIRECT_DISABLED=true     # When true, direct SNS notifications are ignored, only SQS is used
SQS_ENABLED=true             # When true, SQS processing is enabled  
SQS_QUEUE_URL=<url>          # The URL of your SQS queue
SES_CONFIGURATION_SET=<name> # The SES configuration set that sends notifications
```

## Troubleshooting Common Issues

1. **No notifications received**: 
   - Verify the SNS topic is correctly subscribed to your SES Configuration Set
   - Confirm the SQS queue has the correct permissions to receive messages from SNS
   
2. **Notifications not processing**:
   - Check that SQS_ENABLED is set to true in your environment
   - Run the SQS jobs processor manually to troubleshoot: `python sqs_jobs.py`
   
3. **Database not updating**:
   - Check log files for database errors during notification processing
   - Verify message_id is being correctly passed from SES to your application

4. **Server overload during large campaigns**:
   - Review token bucket rate limiting parameters 
   - Consider enabling more aggressive sampling for non-critical notifications
   - Break very large campaigns (10,000+ recipients) into multiple smaller batches
