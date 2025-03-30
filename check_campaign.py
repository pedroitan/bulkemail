"""
Check Campaign State

This script checks the state of a campaign and its recipients
to help diagnose why emails might not be sending.
"""

from app import app
from models import EmailCampaign, EmailRecipient

def check_campaign(campaign_id):
    with app.app_context():
        # Check if the campaign exists
        campaign = EmailCampaign.query.get(campaign_id)
        if not campaign:
            print(f"Campaign {campaign_id} does not exist!")
            return
        
        print(f"\nCAMPAIGN DETAILS:")
        print(f"ID: {campaign.id}")
        print(f"Name: {campaign.name}")
        print(f"Status: {campaign.status}")
        print(f"Subject: {campaign.subject}")
        
        # Check recipients
        recipients = EmailRecipient.query.filter_by(campaign_id=campaign_id).all()
        recipient_count = len(recipients)
        print(f"\nRECIPIENTS: {recipient_count}")
        
        if recipient_count == 0:
            print("⚠️ This campaign has no recipients! Add recipients before sending.")
            return
        
        # Count recipients by status
        statuses = {}
        delivery_statuses = {}
        
        for r in recipients:
            if r.status not in statuses:
                statuses[r.status] = 0
            statuses[r.status] += 1
            
            if r.delivery_status not in delivery_statuses:
                delivery_statuses[r.delivery_status] = 0
            delivery_statuses[r.delivery_status] += 1
        
        print("\nSTATUS BREAKDOWN:")
        for status, count in statuses.items():
            print(f"  {status}: {count}")
            
        print("\nDELIVERY STATUS BREAKDOWN:")
        for status, count in delivery_statuses.items():
            print(f"  {status}: {count}")
            
        print("\nSAMPLE RECIPIENTS:")
        for r in recipients[:5]:  # Show first 5 recipients
            print(f"  {r.email} - Status: {r.status}, Delivery: {r.delivery_status}")
        
        if recipient_count > 5:
            print(f"  ... and {recipient_count - 5} more")
        
        # Check campaign body
        print("\nCAMPAIGN BODY PREVIEW:")
        if campaign.body_html:
            preview = campaign.body_html[:100] + "..." if len(campaign.body_html) > 100 else campaign.body_html
            print(f"  {preview}")
        else:
            print("  ⚠️ Empty campaign body!")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        campaign_id = int(sys.argv[1])
    else:
        campaign_id = 1  # Default to campaign 1
    
    check_campaign(campaign_id)
