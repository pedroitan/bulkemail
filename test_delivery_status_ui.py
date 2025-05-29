import boto3
import json
import time
import os
import uuid
import requests
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# AWS configuration
aws_region = os.getenv('AWS_REGION', 'us-east-2')
aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
sqs_queue_url = os.getenv('SQS_QUEUE_URL')
sender_email = os.getenv('SENDER_EMAIL')
ses_configuration_set = os.getenv('SES_CONFIGURATION_SET')

# Database path
database_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.db')

# Create AWS clients
ses_client = boto3.client('ses', 
                         region_name=aws_region,
                         aws_access_key_id=aws_access_key,
                         aws_secret_access_key=aws_secret_key)

sqs_client = boto3.client('sqs', 
                         region_name=aws_region,
                         aws_access_key_id=aws_access_key,
                         aws_secret_access_key=aws_secret_key)

def send_test_email():
    """Send a test email with tracking enabled"""
    recipient_email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    subject = f"Test Email - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    message_id = None
    
    try:
        # Create a unique test email
        response = ses_client.send_email(
            Source=sender_email,
            Destination={
                'ToAddresses': [recipient_email]
            },
            Message={
                'Subject': {
                    'Data': subject
                },
                'Body': {
                    'Text': {
                        'Data': f"This is a test email to verify delivery status updates. Timestamp: {datetime.now().isoformat()}"
                    },
                    'Html': {
                        'Data': f"""
                        <html>
                        <body>
                            <h1>Test Email</h1>
                            <p>This is a test email to verify delivery status updates.</p>
                            <p>Timestamp: {datetime.now().isoformat()}</p>
                        </body>
                        </html>
                        """
                    }
                }
            },
            ConfigurationSetName=ses_configuration_set  # Important for tracking
        )
        
        message_id = response.get('MessageId')
        logger.info(f"✅ Successfully sent test email to {recipient_email} with message ID: {message_id}")
        
        # Add this test email to the database for tracking
        try:
            conn = sqlite3.connect(database_path)
            cursor = conn.cursor()
            
            # Insert a test campaign
            campaign_id = add_test_campaign(cursor)
            
            # Insert the recipient
            cursor.execute('''
                INSERT INTO recipient (email, status, created_at, campaign_id)
                VALUES (?, ?, ?, ?)
            ''', (recipient_email, 'sent', datetime.now().isoformat(), campaign_id))
            
            recipient_id = cursor.lastrowid
            
            # Insert email tracking info
            cursor.execute('''
                INSERT INTO email_tracking (recipient_id, message_id, status, created_at)
                VALUES (?, ?, ?, ?)
            ''', (recipient_id, message_id, 'sent', datetime.now().isoformat()))
            
            conn.commit()
            logger.info(f"✅ Added test email to database with recipient ID: {recipient_id}")
            
            return {
                'message_id': message_id,
                'recipient_email': recipient_email,
                'recipient_id': recipient_id,
                'campaign_id': campaign_id
            }
        except Exception as e:
            logger.error(f"❌ Error adding test email to database: {str(e)}")
            return {'message_id': message_id, 'recipient_email': recipient_email}
        finally:
            if conn:
                conn.close()
    
    except Exception as e:
        logger.error(f"❌ Error sending test email: {str(e)}")
        return None

def add_test_campaign(cursor):
    """Add a test campaign to the database"""
    campaign_name = f"Test Campaign - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    cursor.execute('''
        INSERT INTO campaign (name, status, created_at)
        VALUES (?, ?, ?)
    ''', (campaign_name, 'sent', datetime.now().isoformat()))
    
    return cursor.lastrowid

def monitor_sqs_for_delivery_notification(message_info, timeout=300):
    """Monitor SQS queue for delivery notification for up to 5 minutes"""
    start_time = time.time()
    target_message_id = message_info.get('message_id')
    
    logger.info(f"Monitoring SQS for delivery notification for message ID: {target_message_id}")
    logger.info(f"Will monitor for up to {timeout} seconds...")
    
    while time.time() - start_time < timeout:
        try:
            # Receive messages from SQS queue
            response = sqs_client.receive_message(
                QueueUrl=sqs_queue_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=20,  # Long polling
                AttributeNames=['All'],
                MessageAttributeNames=['All']
            )
            
            messages = response.get('Messages', [])
            
            if messages:
                logger.info(f"Received {len(messages)} message(s) from SQS queue")
                
                for message in messages:
                    message_id = message.get('MessageId')
                    receipt_handle = message.get('ReceiptHandle')
                    body = message.get('Body')
                    
                    # Parse message body (SNS notification wrapped in SQS message)
                    try:
                        body_json = json.loads(body)
                        sns_message = body_json.get('Message', '')
                        
                        if sns_message:
                            try:
                                sns_message_json = json.loads(sns_message)
                                notification_type = sns_message_json.get('notificationType')
                                
                                if notification_type:
                                    logger.info(f"Found {notification_type} notification")
                                    
                                    # Check if this is for our test message
                                    mail_info = sns_message_json.get('mail', {})
                                    ses_message_id = mail_info.get('messageId')
                                    
                                    if ses_message_id == target_message_id:
                                        logger.info(f"✅ Found {notification_type} notification for our test message!")
                                        
                                        # Delete message after processing
                                        sqs_client.delete_message(
                                            QueueUrl=sqs_queue_url,
                                            ReceiptHandle=receipt_handle
                                        )
                                        
                                        return {
                                            'notification_type': notification_type,
                                            'message_id': ses_message_id,
                                            'timestamp': time.time()
                                        }
                                    else:
                                        logger.info(f"This notification is for a different message ID: {ses_message_id}")
                            except json.JSONDecodeError:
                                logger.warning(f"SNS message is not valid JSON")
                    except json.JSONDecodeError:
                        logger.warning(f"Message body is not valid JSON")
                    
                    # Delete message after processing
                    sqs_client.delete_message(
                        QueueUrl=sqs_queue_url,
                        ReceiptHandle=receipt_handle
                    )
            else:
                logger.info(f"No messages found in SQS queue, continuing to monitor... ({int(time.time() - start_time)}s elapsed)")
            
            # Wait a bit before polling again
            time.sleep(10)
        
        except Exception as e:
            logger.error(f"❌ Error receiving messages from SQS queue: {str(e)}")
            time.sleep(10)
    
    logger.warning(f"⚠️ Timeout reached. No delivery notification found for message ID: {target_message_id}")
    return None

def check_database_for_status_update(message_info, delivery_info=None):
    """Check if the status was updated in the database"""
    recipient_id = message_info.get('recipient_id')
    message_id = message_info.get('message_id')
    
    if not recipient_id or not message_id:
        logger.warning("Missing recipient_id or message_id, can't check database")
        return False
    
    try:
        conn = sqlite3.connect(database_path)
        cursor = conn.cursor()
        
        # Query for updates to the email_tracking table
        cursor.execute('''
            SELECT status, updated_at
            FROM email_tracking
            WHERE recipient_id = ? AND message_id = ?
            ORDER BY updated_at DESC
        ''', (recipient_id, message_id))
        
        results = cursor.fetchall()
        
        if results:
            latest_status = results[0][0]
            latest_update = results[0][1]
            
            logger.info(f"✅ Found status in database: {latest_status} (updated at: {latest_update})")
            
            # If we found a delivery notification and the status matches
            if delivery_info and delivery_info.get('notification_type') == 'Delivery' and latest_status == 'delivered':
                logger.info(f"✅ SUCCESS: Status was correctly updated to 'delivered' in the database!")
                return True
            elif latest_status != 'sent':
                logger.info(f"✅ Status was updated from 'sent' to '{latest_status}' in the database")
                return True
            else:
                logger.warning(f"⚠️ Status is still 'sent' in the database, no update detected")
                return False
        else:
            logger.warning(f"⚠️ No email_tracking entry found for recipient_id={recipient_id}, message_id={message_id}")
            return False
    
    except Exception as e:
        logger.error(f"❌ Error checking database for status update: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()

def test_delivery_status_update():
    """Run a comprehensive test for delivery status updates"""
    logger.info("=== TESTING DELIVERY STATUS UPDATES IN UI ===")
    
    # Step 1: Send a test email
    logger.info("\n=== STEP 1: SENDING TEST EMAIL ===")
    message_info = send_test_email()
    
    if not message_info:
        logger.error("❌ Failed to send test email, aborting test")
        return
    
    # Step 2: Monitor SQS for delivery notification
    logger.info("\n=== STEP 2: MONITORING SQS FOR DELIVERY NOTIFICATION ===")
    delivery_info = monitor_sqs_for_delivery_notification(message_info)
    
    # Step 3: Check if status was updated in database/UI
    logger.info("\n=== STEP 3: CHECKING STATUS UPDATE IN DATABASE ===")
    db_updated = check_database_for_status_update(message_info, delivery_info)
    
    # Summary
    logger.info("\n=== TEST SUMMARY ===")
    logger.info(f"Test Email Sent: {'✅ Yes' if message_info else '❌ No'}")
    logger.info(f"Delivery Notification Received: {'✅ Yes' if delivery_info else '❌ No'}")
    logger.info(f"Database Status Updated: {'✅ Yes' if db_updated else '❌ No'}")
    
    if message_info and delivery_info and db_updated:
        logger.info("\n✅✅✅ TEST PASSED! The entire SES → SNS → SQS → UI flow is working correctly!")
        logger.info("Your email delivery status updates are successfully flowing through the system.")
    else:
        logger.warning("\n⚠️ TEST INCOMPLETE: Some parts of the flow may still need attention.")
        
        if not delivery_info:
            logger.info("Suggestions:")
            logger.info("1. The SQS job might not be processing messages - check sqs_jobs.py")
            logger.info("2. Your token bucket rate limiter might be limiting delivery notifications - check app.py")
            logger.info("3. SES might be sending notifications to a different SNS topic - check your SES configuration")
        
        if not db_updated and delivery_info:
            logger.info("Suggestions:")
            logger.info("1. The database update code might not be working - check sns notification handler in app.py")
            logger.info("2. There might be an error in the notification processing logic")

if __name__ == "__main__":
    test_delivery_status_update()
