# AWS SNS Setup Guide for Email Notifications

## Problem Identified

Your application is correctly sending emails, but it's not receiving the delivery status notifications from AWS SNS. This is happening because AWS SNS is not properly configured to send notifications to your ngrok URL.

## Configure AWS SNS Subscription

1. **Log in to AWS Console** and navigate to the SNS service

2. **Select your SNS Topic** that's configured for SES notifications

3. **Update or Create a Subscription** with the following settings:
   - Protocol: HTTPS
   - Endpoint: `https://7295-2804-214-11-2260-e125-7aed-8917-3ca.ngrok-free.app/api/sns/ses-notification`
   - Make sure you're using the exact path: `/api/sns/ses-notification`

4. **Verify the subscription**:
   - When you create the subscription, AWS SNS will send a confirmation request to your endpoint
   - Your application is already configured to automatically confirm this subscription
   - Check your application logs for a message like "SNS subscription confirmed"

## Configure AWS SES Configuration Set

1. In the AWS SES console, go to **Configuration Sets**

2. **Create a Configuration Set** named `email-tracking` (this must match the name in your .env file)

3. **Add an Event Destination**:
   - Select SNS as the event destination type
   - Connect it to your SNS topic
   - Enable these event types: Sends, Deliveries, Bounces, Complaints

## Testing Your Setup

1. After configuring SNS and SES, send a test email using:
   ```
   python test_notifications.py --email=success@simulator.amazonses.com --campaign=1 --test=delivery
   ```

2. Check your application logs for:
   - `======= SNS NOTIFICATION RECEIVED =======` (confirms AWS SNS is hitting your endpoint)
   - `Processed Delivery notification` (confirms successful processing)

3. Verify the delivery status in your UI is updated 

## Important Notes

1. **Ngrok URL Changes**: If you restart ngrok, you'll get a new URL and need to update your SNS subscription

2. **AWS SES Testing**: Amazon SES provides test email addresses you can use:
   - success@simulator.amazonses.com (for delivery notifications)
   - bounce@simulator.amazonses.com (for bounce notifications)
   - complaint@simulator.amazonses.com (for complaint notifications)

3. **Debugging Tips**:
   - Check your AWS SNS subscription status (should be "Confirmed")
   - Enable AWS SNS delivery status logging in your AWS console
   - Monitor the application logs for incoming SNS requests
