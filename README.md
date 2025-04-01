# Bulk Email Scheduler with Amazon SES

A web application for scheduling and sending bulk emails using Amazon SES (Simple Email Service) with advanced tracking, notification handling, and verification capabilities. The application uses a robust SNS-SQS notification flow to reliably process email delivery events even for large campaigns.

## Features

- Create and schedule email campaigns
- Upload recipients from CSV or Excel files
- Personalize emails with recipient data using template variables
- Track email sending status and campaign progress
- Send test emails before launching campaigns
- Rate-limited sending to prevent AWS throttling
- Responsive dashboard for monitoring campaign performance
- **Email bounce tracking** with detailed diagnostics
- **Email verification** to reduce bounces and protect sender reputation
- **Open and click tracking** to monitor recipient engagement
- **Comprehensive event handling** for all SES notification types (Bounce, Complaint, Delivery, DeliveryDelay, Send)
- **Real-time delivery status updates** using AWS SNS-SQS notification flow
- **Robust large campaign handling** for reliably sending thousands of emails 
- **Rate-limited notification processing** to prevent server overload

## Architecture

The application is built with a modern architecture focusing on reliability and scalability:

- **Lazy Initialization Pattern**: Components like the email service and scheduler are initialized only when needed, preventing issues when working outside the Flask application context
- **Non-blocking UI**: Form-based operations for critical actions with automatic page refresh
- **Real-time Updates**: Auto-refreshing tables show delivery status changes without requiring page reload
- **AWS Integration**: Seamless integration with AWS SES for sending and AWS SNS for tracking
- **SQS Message Processing**: Resilient SQS-based notification handling for all event types (Send, Delivery, Bounce, Complaint, DeliveryDelay)
- **Rate Limiting**: Token bucket rate limiter for SNS notifications to prevent server overload during large campaigns
- **Adaptive Notification Handling**: Intelligent handling of notifications based on campaign size
- **Enhanced Worker Configuration**: Optimized Gunicorn settings for handling large campaigns
- **Synchronous Processing**: Efficient processing of email campaigns without requiring separate worker processes

## Setup

### Prerequisites

- Python 3.8+ installed
- AWS account with SES access
- AWS account with SNS access (for event notifications)
- AWS account with SQS access (for processing notifications)
- Verified email address or domain in SES
- AWS access key and secret key with appropriate permissions (SES, SNS, SQS)

### Installation

1. Clone the repository or download the source code:
   ```
   git clone <repository-url>
   cd emailbulk
   ```

2. Create a virtual environment:
   ```
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env` and configure your environment variables:
   ```
   cp .env.example .env
   ```
   
   Edit the `.env` file with your AWS credentials and other configuration settings:
   ```
   # AWS Credentials
   AWS_ACCESS_KEY_ID=your_access_key
   AWS_SECRET_ACCESS_KEY=your_secret_key
   AWS_REGION=your_aws_region
   
   # Email Configuration
   SENDER_EMAIL=your_verified_email@example.com
   MAX_EMAILS_PER_SECOND=10
   SES_CONFIGURATION_SET=email-tracking  # Optional: For advanced delivery tracking
   
   # Application Settings
   FLASK_APP=app.py
   FLASK_ENV=development
   SECRET_KEY=your_secret_key
   ```

5. Initialize the database and run the update script:
   ```
   source .venv/bin/activate
   python update_db_schema.py
   ```

6. Run the application:
   ```
   flask run
   ```

7. Visit `http://localhost:5000` in your browser to access the application

## AWS Setup

### SES (Simple Email Service) Setup

1. Sign in to your AWS account and navigate to the SES service
2. If your account is in sandbox mode (default for new accounts):
   - You can only send to verified email addresses
   - You can request production access from the SES console
3. Verify your sender email address or domain:
   - Go to "Verified Identities" in the SES console
   - Click "Create Identity" and follow the verification process
4. Create an IAM user with the following permissions:
   - `ses:SendEmail`
   - `ses:SendRawEmail`
5. Generate access keys for this user and add them to your `.env` file

### SNS (Simple Notification Service) Setup for Bounce Tracking

1. In the AWS Management Console, navigate to SES
2. Go to the "Configuration Sets" section
3. Create a new configuration set named "email-tracking" (or use your preferred name and update the .env file)
4. Add an SNS destination for bounce, complaint, and delivery events
5. Create a new SNS topic for these events or use an existing one
6. Make sure your IAM user has permissions to publish to this SNS topic
7. Set up an HTTP endpoint to receive SNS notifications:
   - For local development, you can use ngrok to create a public URL that forwards to your local server
   - Run `ngrok http 5000` to create a tunnel
   - Use the ngrok URL (e.g., https://your-ngrok-id.ngrok.io/sns-notifications) as the SNS subscription endpoint

## Using the Application

### Creating a Campaign

1. Log in to the application
2. Click on "New Campaign" in the sidebar
3. Fill in the campaign details:
   - Name your campaign
   - Enter the email subject
   - Create your email content using the HTML editor
   - You can use template variables like {{name}} or {{email}} for personalization
4. Click "Save Campaign" to proceed

### Adding Recipients

1. From your campaign details page, click "Upload Recipients"
2. You can upload a CSV or Excel file with recipient information
3. The file should have at least an "email" column
4. Additional columns can be used as template variables in your email
5. After uploading, you can verify recipients to check for potential bounces

### Testing Your Campaign

1. From the campaign details page, click "Send Test Email"
2. Enter your email address or use the AWS SES simulator addresses:
   - success@simulator.amazonses.com (for successful delivery)
   - bounce@simulator.amazonses.com (to simulate a bounce)
   - complaint@simulator.amazonses.com (to simulate a complaint)
3. Review the test email to ensure your content and formatting are correct

### Launching Your Campaign

1. Return to the campaign details page
2. Verify that all settings are correct
3. Click "Start Sending" to begin sending the campaign
4. The status will update in real-time as emails are sent
5. Delivery status updates will appear automatically as they are received from AWS

### Monitoring Campaigns

1. The dashboard shows an overview of all campaigns and their status
2. Each campaign detail page shows:
   - Delivery statistics
   - Bounces and complaints
   - Individual recipient status

## Handling Large Campaigns

The system includes special optimizations for handling large email campaigns (100+ recipients):

### Automatic Notification Management

- For campaigns with more than 100 recipients, the system automatically adjusts SES notification settings to prevent server overload
- Critical notifications (bounces, complaints) are always processed, while less important notifications may be rate-limited or disabled
- This prevents 502 Bad Gateway errors that can occur when processing thousands of notifications simultaneously

### Rate Limiting Implementation

- A token bucket rate limiter manages the flow of SNS notifications to the server
- This ensures the server remains responsive even during high-volume campaigns
- The rate limiter prioritizes critical notifications (bounces, complaints) over delivery notifications

### Sending Best Practices

When sending large campaigns (1,000+ recipients):

1. **Batch Processing**: Break extremely large campaigns into smaller batches of 1,000-3,000 recipients
2. **Monitoring**: Keep an eye on the campaign progress and notification logs
3. **Scheduling**: Send large campaigns during off-peak hours to minimize impact on other operations
4. **Testing**: Always test with a small subset of recipients before launching the full campaign

### Server Configuration

The application uses optimized Gunicorn settings for handling large workloads:

- Extended worker timeout (120 seconds) to prevent timeout errors during high-volume processing
- Worker recycling to prevent memory issues during long-running campaigns
- Multiple workers to handle concurrent requests efficiently

## Troubleshooting

### Email Sending Issues

- Check your AWS SES limits and account status
- Verify that your sender email is verified in SES
- Ensure your AWS credentials have the necessary permissions
- Check the application logs for any error messages
- Run the diagnostic script: `python debug_email_flow.py`

### SNS Notification Issues

- Confirm your ngrok tunnel is running and accessible
- Verify that the SNS subscription is confirmed
- Check that the configuration set is properly set up in SES
- Ensure your IAM user has permissions to receive notifications
- Review the SNS subscription settings in the AWS console

### Large Campaign Issues

- If you encounter 502 errors during large campaigns, check the server logs for notification volume
- Consider breaking very large campaigns (10,000+ recipients) into smaller batches
- Verify your Render service plan has sufficient resources for your campaign volume
- Use the `DISABLE_TRACKING_THRESHOLD` environment variable to adjust when notification tracking is disabled (default: 100)

## Performance Considerations

### Memory Usage

- The application is designed to minimize memory usage during large campaigns
- Email sending occurs in batches with small delays to prevent server overload
- Worker processes are recycled after handling a certain number of requests to prevent memory leaks

### Notification Processing

- SNS notifications are processed with a token bucket rate limiter (10 notifications per second)
- Critical notifications (bounces, complaints) bypass the rate limiter to ensure delivery status is accurately tracked
- For campaigns over 100 recipients, most delivery notifications are automatically disabled to reduce server load

### Scaling Guidelines

| Campaign Size | Recommended Configuration                                      |
|---------------|---------------------------------------------------------------|
| < 100         | Default settings with full notification tracking               |
| 100 - 1,000   | Automatic notification limitation for non-critical events      |
| 1,000 - 5,000 | Break into multiple batches of 1,000 recipients               |
| > 5,000       | Consider upgrading Render plan or using a dedicated server     |

## Development

### Environment Setup

- Use `.env.development` for development settings
- Create `.env.production` for production settings
- Never commit these files to version control

### Testing Locally

- Use AWS SES simulator addresses for testing without sending real emails
- For SNS notifications testing with ngrok:
  ```
  ngrok http 5000
  ```

### Running Tests

```
python -m pytest tests/
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Amazon Web Services for SES and SNS services
- Flask and its ecosystem for web framework components
- The open-source community for various libraries and tools used in this project
