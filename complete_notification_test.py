"""
Complete Notification Flow Test Script

This script tests the entire notification flow:
1. Sends a test email to bounce@simulator.amazonses.com
2. Creates the bounce notification manually
3. Verifies database update
4. Tests the API endpoint for recipient data
5. Reports final results
"""

from app import app
from models import db, EmailCampaign, EmailRecipient
from email_service import SESEmailService
import json
import time
import requests
import uuid
from datetime import datetime

class NotificationTest:
    def __init__(self, campaign_id, test_email):
        self.campaign_id = campaign_id
        self.test_email = test_email
        self.message_id = str(uuid.uuid4())
        self.recipient_id = None
        self.tests_passed = 0
        self.tests_total = 5

    def run_tests(self):
        print(f"\n{'='*20} NOTIFICATION FLOW TEST {'='*20}")
        print(f"Campaign ID: {self.campaign_id}")
        print(f"Test Email: {self.test_email}")
        print(f"{'='*60}\n")
        
        try:
            with app.app_context():
                self.test_1_prepare_recipient()
                self.test_2_send_email()
                self.test_3_simulate_notification()
                self.test_4_verify_database()
                self.test_5_test_api_endpoint()
                
                self.print_results()
        except Exception as e:
            print(f"\n❌ ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def test_1_prepare_recipient(self):
        print("\n🔍 TEST 1: PREPARING TEST RECIPIENT")
        try:
            # Get campaign
            campaign = EmailCampaign.query.get(self.campaign_id)
            if not campaign:
                raise ValueError(f"Campaign {self.campaign_id} not found!")
            
            # Create or reset test recipient
            recipient = EmailRecipient.query.filter_by(
                campaign_id=self.campaign_id, 
                email=self.test_email
            ).first()
            
            if recipient:
                print(f"Resetting existing test recipient: {self.test_email}")
                recipient.status = 'pending'
                recipient.delivery_status = 'pending'
                recipient.sent_at = None
                recipient.bounce_type = None
                recipient.bounce_subtype = None
                recipient.bounce_time = None
                recipient.bounce_diagnostic = None
            else:
                print(f"Creating new test recipient: {self.test_email}")
                recipient = EmailRecipient(
                    campaign_id=self.campaign_id,
                    email=self.test_email,
                    name="Test Recipient",
                    status='pending',
                    delivery_status='pending'
                )
                db.session.add(recipient)
            
            db.session.commit()
            self.recipient_id = recipient.id
            print(f"✅ PASS: Test recipient prepared successfully (ID: {self.recipient_id})")
            self.tests_passed += 1
        except Exception as e:
            print(f"❌ FAIL: Could not prepare test recipient: {str(e)}")
    
    def test_2_send_email(self):
        print("\n🔍 TEST 2: SENDING TEST EMAIL")
        try:
            # Get campaign and recipient
            campaign = EmailCampaign.query.get(self.campaign_id)
            recipient = EmailRecipient.query.get(self.recipient_id)
            
            # Initialize email service
            email_service = SESEmailService()
            
            # Send test email
            print(f"Sending test email to {self.test_email}...")
            message_id = email_service.send_email(
                recipient=self.test_email,
                subject=f"Test Email for {campaign.name}",
                body_html=f"<p>This is a test email for campaign {campaign.name}</p>",
                sender=campaign.sender_email,
                sender_name=campaign.sender_name
            )
            
            if not message_id:
                raise ValueError("Failed to send email (No message ID returned)")
            
            self.message_id = message_id
            print(f"Message ID: {self.message_id}")
            
            # Update recipient status
            recipient.status = 'sent'
            recipient.delivery_status = 'sent'
            recipient.sent_at = datetime.now()
            recipient.message_id = self.message_id
            db.session.commit()
            
            print(f"Initial status: {recipient.status}")
            print(f"Initial delivery status: {recipient.delivery_status}")
            
            print(f"✅ PASS: Test email sent successfully")
            self.tests_passed += 1
            
            # Small wait to ensure AWS processes the email
            print("Waiting 2 seconds...")
            time.sleep(2)
            
        except Exception as e:
            print(f"❌ FAIL: Could not send test email: {str(e)}")
    
    def test_3_simulate_notification(self):
        print("\n🔍 TEST 3: SIMULATING NOTIFICATION")
        try:
            notification_type = "bounce" if "bounce" in self.test_email else "delivery"
            
            # Create the notification payload
            if notification_type == "bounce":
                print(f"Simulating bounce notification for {self.test_email}...")
                # Create bounce notification payload in the exact format AWS SNS expects
                notification = {
                    "notificationType": "Bounce",
                    "mail": {
                        "timestamp": datetime.now().isoformat(),
                        "messageId": self.message_id,
                        "source": "test@example.com",
                        "destination": [self.test_email]
                    },
                    "bounce": {
                        "bounceType": "Permanent",
                        "bounceSubType": "General",
                        "bouncedRecipients": [{
                            "emailAddress": self.test_email,
                            "action": "failed",
                            "status": "5.1.1",
                            "diagnosticCode": "Test bounce notification"
                        }],
                        "timestamp": datetime.now().isoformat(),
                        "feedbackId": "0100017123456789-12345678-9012-3456-7890-123456789012-000000"
                    }
                }
                
                # Send to the SNS endpoint as an HTTP request in the exact format AWS SNS uses
                sns_payload = {
                    "Type": "Notification",
                    "MessageId": str(uuid.uuid4()),
                    "TopicArn": "arn:aws:sns:us-east-1:123456789012:ses-bounces",
                    "Subject": "Amazon SES Email Event Notification",
                    "Message": json.dumps(notification),
                    "Timestamp": datetime.now().isoformat(),
                    "SignatureVersion": "1",
                    "Signature": "test-signature",
                    "SigningCertURL": "https://sns.us-east-1.amazonaws.com/SimpleNotificationService-12345.pem",
                    "UnsubscribeURL": "https://sns.us-east-1.amazonaws.com/?Action=Unsubscribe&SubscriptionArn=test"
                }
                
                response = requests.post(
                    "http://localhost:5000/api/sns/ses-notification", 
                    json=sns_payload,
                    headers={"Content-Type": "application/json"}
                )
            else:
                print(f"Simulating delivery notification for {self.test_email}...")
                # Create delivery notification payload in the exact format AWS SNS expects
                notification = {
                    "notificationType": "Delivery",
                    "mail": {
                        "timestamp": datetime.now().isoformat(),
                        "messageId": self.message_id,
                        "source": "test@example.com",
                        "destination": [self.test_email]
                    },
                    "delivery": {
                        "timestamp": datetime.now().isoformat(),
                        "processingTimeMillis": 500,
                        "recipients": [self.test_email],
                        "smtpResponse": "250 2.6.0 Message received",
                        "reportingMTA": "test.mta.example.com",
                        "remoteMtaIp": "127.0.0.1"
                    }
                }
                
                # Send to the SNS endpoint as an HTTP request in the exact format AWS SNS uses
                sns_payload = {
                    "Type": "Notification",
                    "MessageId": str(uuid.uuid4()),
                    "TopicArn": "arn:aws:sns:us-east-1:123456789012:ses-deliveries",
                    "Subject": "Amazon SES Email Event Notification",
                    "Message": json.dumps(notification),
                    "Timestamp": datetime.now().isoformat(),
                    "SignatureVersion": "1",
                    "Signature": "test-signature",
                    "SigningCertURL": "https://sns.us-east-1.amazonaws.com/SimpleNotificationService-12345.pem",
                    "UnsubscribeURL": "https://sns.us-east-1.amazonaws.com/?Action=Unsubscribe&SubscriptionArn=test"
                }
                
                response = requests.post(
                    "http://localhost:5000/api/sns/ses-notification", 
                    json=sns_payload,
                    headers={"Content-Type": "application/json"}
                )
            
            if response.status_code != 200:
                raise ValueError(f"Notification API returned status code {response.status_code}: {response.text}")
            
            print(f"Notification sent successfully!")
            
            # Wait more time for processing with multiple checks
            print("Waiting for notification processing...")
            max_retries = 5
            retry_count = 0
            
            while retry_count < max_retries:
                # Check if the status has been updated
                recipient = None
                with app.app_context():
                    recipient = EmailRecipient.query.get(self.recipient_id)
                
                expected_status = "bounced" if "bounce" in self.test_email else "delivered"
                if recipient and recipient.delivery_status == expected_status:
                    break
                
                # Wait before retry
                time.sleep(1)
                retry_count += 1
                print(f"Retry {retry_count}/{max_retries}...")
            
            print(f"✅ PASS: Notification simulation completed")
            self.tests_passed += 1
            
        except Exception as e:
            print(f"❌ FAIL: Could not simulate notification: {str(e)}")
    
    def test_4_verify_database(self):
        print("\n🔍 TEST 4: VERIFYING DATABASE UPDATE")
        try:
            # Get updated recipient
            recipient = EmailRecipient.query.get(self.recipient_id)
            
            print(f"Current status: {recipient.status}")
            print(f"Current delivery status: {recipient.delivery_status}")
            print(f"Message ID: {recipient.message_id}")
            
            if "bounce" in self.test_email:
                if recipient.delivery_status != "bounced" or recipient.status != "failed":
                    raise ValueError(f"Recipient not updated correctly. Expected delivery_status='bounced', status='failed', got delivery_status='{recipient.delivery_status}', status='{recipient.status}'")
                
                print(f"Bounce type: {recipient.bounce_type}")
                print(f"Bounce subtype: {recipient.bounce_subtype}")
                print(f"Bounce diagnostic: {recipient.bounce_diagnostic}")
                
                print(f"✅ PASS: Bounce status was correctly updated")
            else:
                if recipient.delivery_status != "delivered":
                    raise ValueError(f"Recipient not updated correctly. Expected delivery_status='delivered', got '{recipient.delivery_status}'")
                
                print(f"✅ PASS: Delivery status was correctly updated to 'delivered'")
            
            self.tests_passed += 1
        except Exception as e:
            print(f"❌ FAIL: Database verification failed: {str(e)}")
    
    def test_5_test_api_endpoint(self):
        print("\n🔍 TEST 5: TESTING API ENDPOINT")
        try:
            # Get data from API endpoint
            response = requests.get(f"http://localhost:5000/api/campaigns/{self.campaign_id}/recipients")
            if response.status_code != 200:
                raise ValueError(f"API returned status code {response.status_code}")
            
            data = response.json()
            if not data.get('success'):
                raise ValueError(f"API returned error: {data.get('message')}")
            
            # Find our test recipient
            recipient_data = None
            for r in data['recipients']:
                if r['email'] == self.test_email and r['id'] == self.recipient_id:
                    recipient_data = r
                    break
            
            if not recipient_data:
                raise ValueError(f"Test recipient not found in API response")
            
            # Verify data
            if "bounce" in self.test_email:
                if recipient_data['delivery_status'] != "bounced" or recipient_data['status'] != "failed":
                    raise ValueError(f"API data not updated correctly. Expected delivery_status='bounced', status='failed', got delivery_status='{recipient_data['delivery_status']}', status='{recipient_data['status']}'")
            else:
                if recipient_data['delivery_status'] != "delivered":
                    raise ValueError(f"API data not updated correctly. Expected delivery_status='delivered', got '{recipient_data['delivery_status']}'")
            
            print(f"✅ PASS: API endpoint data is correct and matches database")
            self.tests_passed += 1
        except Exception as e:
            print(f"❌ FAIL: API endpoint test failed: {str(e)}")
    
    def print_results(self):
        print(f"\n{'='*20} TEST RESULTS {'='*20}")
        print(f"Tests Passed: {self.tests_passed}/{self.tests_total}")
        
        if self.tests_passed == self.tests_total:
            print(f"\n🎉 SUCCESS: All tests passed!")
            print("Your notification system is working correctly.")
        else:
            print(f"\n❌ SOME TESTS FAILED: {self.tests_total - self.tests_passed} tests failed")
            print("Check the logs above for details.")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python complete_notification_test.py [bounce|delivery]")
        sys.exit(1)
    
    test_type = sys.argv[1]
    if test_type not in ['bounce', 'delivery']:
        print("Test type must be 'bounce' or 'delivery'")
        sys.exit(1)
    
    campaign_id = 1  # Use the campaign ID from your database
    
    if test_type == 'bounce':
        test_email = "bounce@simulator.amazonses.com"
    else:
        test_email = "success@simulator.amazonses.com"
    
    tester = NotificationTest(campaign_id, test_email)
    tester.run_tests()
