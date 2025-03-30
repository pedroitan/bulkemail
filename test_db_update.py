from app import app, handle_delivery_notification, handle_bounce_notification
from models import db, EmailRecipient
import json
import sys

def test_delivery_update():
    with app.app_context():
        # Get the email and message_id from command line arguments
        if len(sys.argv) < 3:
            print("Usage: python test_db_update.py <email> <message_id>")
            sys.exit(1)
            
        email = sys.argv[1]
        message_id = sys.argv[2]
        
        # Check current state
        recipient = EmailRecipient.query.filter_by(email=email).first()
        if not recipient:
            print(f"❌ Recipient {email} not found in database!")
            sys.exit(1)
            
        print(f"Initial status: {recipient.status}")
        print(f"Initial delivery status: {recipient.delivery_status}")
        
        # Create a test delivery notification
        delivery_notification = {
            "mail": {
                "messageId": message_id
            },
            "delivery": {
                "recipients": [email],
                "timestamp": "2025-03-29T15:00:00.000Z"
            }
        }
        
        # Update database
        handle_delivery_notification(delivery_notification)
        
        # Verify the update
        recipient = EmailRecipient.query.filter_by(email=email).first()
        print(f"Updated status: {recipient.status}")
        print(f"Updated delivery status: {recipient.delivery_status}")
        
        if recipient.delivery_status == "delivered":
            print("✅ SUCCESS: Database update function is working correctly")
        else:
            print("❌ FAILED: Database not updated correctly!")

def test_bounce_update():
    with app.app_context():
        # Get the email and message_id from command line arguments
        if len(sys.argv) < 3:
            print("Usage: python test_db_update.py <email> <message_id>")
            sys.exit(1)
            
        email = sys.argv[1]
        message_id = sys.argv[2]
        
        # Check current state
        recipient = EmailRecipient.query.filter_by(email=email).first()
        if not recipient:
            print(f"❌ Recipient {email} not found in database!")
            sys.exit(1)
            
        print(f"Initial status: {recipient.status}")
        print(f"Initial delivery status: {recipient.delivery_status}")
        
        # Create a test bounce notification
        bounce_notification = {
            "mail": {
                "messageId": message_id
            },
            "bounce": {
                "bounceType": "Permanent",
                "bounceSubType": "General",
                "bouncedRecipients": [
                    {
                        "emailAddress": email,
                        "diagnosticCode": "Test bounce from database update test"
                    }
                ],
                "timestamp": "2025-03-29T15:00:00.000Z"
            }
        }
        
        # Update database
        handle_bounce_notification(bounce_notification)
        
        # Verify the update
        recipient = EmailRecipient.query.filter_by(email=email).first()
        print(f"Updated status: {recipient.status}")
        print(f"Updated delivery status: {recipient.delivery_status}")
        
        if recipient.delivery_status == "bounced" and recipient.status == "failed":
            print("✅ SUCCESS: Database update function is working correctly")
        else:
            print("❌ FAILED: Database not updated correctly!")

if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[3] == "bounce":
        test_bounce_update()
    else:
        test_delivery_update()
