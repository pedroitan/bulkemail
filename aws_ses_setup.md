# Setting Up AWS SES Notifications

This guide will help you configure Amazon SES to send email status notifications (delivery, bounce, complaint) to your application.

## 1. Create an SNS Topic

First, create an SNS topic that will receive notifications from SES:

1. Go to the [Amazon SNS Console](https://console.aws.amazon.com/sns/home)
2. Click "Topics" in the left sidebar
3. Click "Create topic"
4. Select "Standard" type
5. Name your topic (e.g., `email-notifications`)
6. Click "Create topic"
7. Note the ARN of your topic (it looks like `arn:aws:sns:us-east-2:123456789012:email-notifications`)

## 2. Create an SES Configuration Set

Next, create a configuration set in SES that will use this SNS topic:

1. Go to the [Amazon SES Console](https://console.aws.amazon.com/ses/home)
2. Click "Configuration sets" in the left sidebar
3. Click "Create configuration set"
4. Name your configuration set (e.g., `email-tracking`)
5. Click "Create configuration set"
6. Click on your newly created configuration set
7. Click "Event destinations" tab
8. Click "Add destination"
9. Select all event types (Sends, Deliveries, Bounces, Complaints)
10. Choose "Amazon SNS" as the destination type
11. Select the SNS topic you created earlier
12. Click "Add destination"

## 3. Update Your Application Configuration

Now, update your application to use this configuration set when sending emails:

1. Open your `.env` file
2. Add the following line:
   ```
   SES_CONFIGURATION_SET=email-tracking
   ```
3. Update your `config.py` file to include this configuration:
   ```python
   SES_CONFIGURATION_SET = os.environ.get('SES_CONFIGURATION_SET')
   ```

4. Modify your `email_service.py` file to use this configuration set:
   ```python
   # In the __init__ method of SESEmailService
   self.configuration_set = None
   
   # In the _ensure_client method
   self.configuration_set = current_app.config.get('SES_CONFIGURATION_SET')
   ```

## 4. Make Your Endpoint Accessible to AWS

For AWS to send notifications to your application, your endpoint needs to be publicly accessible:

### Option 1: Deploy to a Public Server
Deploy your application to a server with a public IP address and domain name.

### Option 2: Use ngrok for Local Testing
For local testing, you can use ngrok to create a temporary public URL:

1. Install ngrok: https://ngrok.com/download
2. Start your Flask application
3. In a separate terminal, run:
   ```
   ngrok http 5000
   ```
4. Note the HTTPS URL provided by ngrok (e.g., `https://a1b2c3d4.ngrok.io`)

## 5. Create an SNS Subscription

Finally, subscribe your application's endpoint to the SNS topic:

1. Go back to the [Amazon SNS Console](https://console.aws.amazon.com/sns/home)
2. Click on your topic
3. Click "Create subscription"
4. Select "HTTPS" as the protocol
5. For the endpoint, enter your application's URL followed by `/api/sns/ses-notification`:
   - If using a public server: `https://yourdomain.com/api/sns/ses-notification`
   - If using ngrok: `https://a1b2c3d4.ngrok.io/api/sns/ses-notification`
6. Click "Create subscription"

AWS will send a confirmation request to your endpoint. Your application is already configured to handle this confirmation automatically.

## 6. Test the Setup

To test if everything is working:

1. Send a test email using your application
2. Check the logs for confirmation that AWS sent a subscription confirmation
3. Send another test email and check if you receive delivery notifications

## Troubleshooting

If you're not receiving notifications:

1. Check your AWS SES console to ensure emails are being sent
2. Verify that your configuration set is being used when sending emails
3. Check the SNS subscription status in the AWS console
4. Look at your application logs for any errors in the notification endpoint
5. Make sure your endpoint is publicly accessible
6. Check AWS CloudWatch logs for any delivery issues

Remember that AWS SES in sandbox mode has limitations. If you're in sandbox mode, you can only send to verified email addresses.
