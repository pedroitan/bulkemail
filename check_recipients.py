#!/usr/bin/env python
import os
import sys
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

# Add the current directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from models import db, EmailCampaign, EmailRecipient
from app import create_app

app = create_app()

with app.app_context():
    print("Checking email recipients in the database...")
    
    # Get all campaigns
    campaigns = EmailCampaign.query.all()
    print(f"Found {len(campaigns)} campaigns")
    
    for campaign in campaigns:
        print(f"\nCampaign ID: {campaign.id}, Name: {campaign.name}, Status: {campaign.status}")
        
        # Get all recipients for this campaign
        recipients = EmailRecipient.query.filter_by(campaign_id=campaign.id).all()
        print(f"  Total recipients: {len(recipients)}")
        
        # Count recipients by status
        pending = sum(1 for r in recipients if r.status == 'pending')
        sent = sum(1 for r in recipients if r.status == 'sent')
        failed = sum(1 for r in recipients if r.status == 'failed')
        
        print(f"  Pending: {pending}, Sent: {sent}, Failed: {failed}")
        
        # Print the first 5 recipients
        print("\n  Sample recipients:")
        for i, recipient in enumerate(recipients[:5]):
            print(f"    {i+1}. Email: {recipient.email}, Status: {recipient.status}")
            print(f"       Name: {recipient.name}")
            print(f"       Custom data: {recipient.custom_data}")
