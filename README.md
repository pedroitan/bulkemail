# Bulk Email Scheduler with Amazon SES

A web application for scheduling and sending bulk emails using Amazon SES (Simple Email Service) with advanced tracking and verification capabilities.

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
- **Real-time delivery status updates** using AWS SNS notifications

## Architecture

The application is built with a modern architecture focusing on reliability and scalability:

- **Lazy Initialization Pattern**: Components like the email service and scheduler are initialized only when needed, preventing issues when working outside the Flask application context
- **Non-blocking UI**: Form-based operations for critical actions with automatic page refresh
- **Real-time Updates**: Auto-refreshing tables show delivery status changes without requiring page reload
- **AWS Integration**: Seamless integration with AWS SES for sending and AWS SNS for tracking

## Setup

### Prerequisites

- Python 3.8+ installed
- AWS account with SES access
- AWS account with SNS access (for bounce notifications)
- Verified email address or domain in SES
- AWS access key and secret key with SES permissions

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

## Deployment

### Deploying to Render

This application is configured for easy deployment to Render using the provided blueprint configuration.

#### Prerequisites

1. A Render account (sign up at [render.com](https://render.com))
2. GitHub repository with your code
3. AWS account with configured SES and SNS services

#### Deployment Steps

1. **Connect your GitHub repository to Render**
   - In the Render dashboard, go to "Blueprints"
   - Click "New Blueprint Instance"
   - Connect your GitHub account and select the repository

2. **Configure environment variables**
   - After Render creates the services defined in `render.yaml`, you'll need to configure secret environment variables
   - For both the web service and worker service, add:
     - `AWS_ACCESS_KEY_ID`
     - `AWS_SECRET_ACCESS_KEY`
     - `AWS_REGION`
     - `SENDER_EMAIL`
     - `SES_CONFIGURATION_SET`

3. **Set up AWS SES for the production domain**
   - Verify your domain in SES
   - Create the appropriate configuration set for tracking
   - Update SNS topics and subscriptions to point to your Render URL

4. **Database migrations**
   - After deployment, you'll need to run database migrations
   - Go to the Render dashboard, select the web service
   - Click "Shell" and run:
   ```
   flask db upgrade
   ```

5. **Testing the deployment**
   - Visit your Render web service URL
   - Verify that you can create campaigns and send test emails
   - Check that the scheduler worker is functioning by monitoring logs

#### Monitoring and Maintenance

- View application logs in the Render dashboard
- Set up custom alerts in Render for error notifications
- Schedule regular database backups

### Local Development After Setting Up for Render

For local development after setting up for Render deployment:

1. Use the `.env.development` file for local settings:
   ```bash
   cp .env.example .env.development
   # Edit .env.development with your local settings
   ```

2. Use the development environment:
   ```bash
   FLASK_ENV=development flask run
   ```

3. For background processing locally:
   ```bash
   FLASK_ENV=development python run_scheduler.py
   ```

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
