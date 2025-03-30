#!/usr/bin/env python3
"""
Command-line management script for Bulk Email Scheduler
"""
import argparse
import sys
import os
from datetime import datetime

# Ensure correct path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import EmailCampaign, EmailRecipient
from email_service import SESEmailService
from scheduler import EmailScheduler

def list_campaigns(args):
    """List all campaigns with their status"""
    with app.app_context():
        campaigns = EmailCampaign.query.all()
        
        if not campaigns:
            print("No campaigns found.")
            return
        
        print(f"\nTotal campaigns: {len(campaigns)}")
        print("-" * 80)
        print(f"{'ID':<5} {'NAME':<30} {'STATUS':<15} {'SCHEDULED':<20} {'RECIPIENTS':<10}")
        print("-" * 80)
        
        for campaign in campaigns:
            recipient_count = EmailRecipient.query.filter_by(campaign_id=campaign.id).count()
            scheduled_time = campaign.scheduled_time.strftime('%Y-%m-%d %H:%M') if campaign.scheduled_time else 'Not scheduled'
            print(f"{campaign.id:<5} {campaign.name[:28]:<30} {campaign.status:<15} {scheduled_time:<20} {recipient_count:<10}")

def show_campaign(args):
    """Show details of a specific campaign"""
    campaign_id = args.id
    
    with app.app_context():
        campaign = EmailCampaign.query.get(campaign_id)
        
        if not campaign:
            print(f"Campaign with ID {campaign_id} not found.")
            return
        
        recipients = EmailRecipient.query.filter_by(campaign_id=campaign.id).all()
        
        print("\nCAMPAIGN DETAILS")
        print("-" * 80)
        print(f"ID:             {campaign.id}")
        print(f"Name:           {campaign.name}")
        print(f"Subject:        {campaign.subject}")
        print(f"Sender:         {campaign.sender_name}")
        print(f"Status:         {campaign.status}")
        print(f"Created:        {campaign.created_at.strftime('%Y-%m-%d %H:%M')}")
        print(f"Scheduled:      {campaign.scheduled_time.strftime('%Y-%m-%d %H:%M') if campaign.scheduled_time else 'Not scheduled'}")
        print(f"Recipients:     {len(recipients)}")
        
        # Count recipients by status
        status_counts = {}
        for recipient in recipients:
            status_counts[recipient.status] = status_counts.get(recipient.status, 0) + 1
        
        print("\nRECIPIENT STATUS")
        print("-" * 80)
        for status, count in status_counts.items():
            print(f"{status.capitalize():<15} {count}")

def change_status(args):
    """Change the status of a campaign"""
    campaign_id = args.id
    new_status = args.status
    
    valid_statuses = ['draft', 'scheduled', 'in_progress', 'completed', 'failed']
    if new_status not in valid_statuses:
        print(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        return
    
    with app.app_context():
        campaign = EmailCampaign.query.get(campaign_id)
        
        if not campaign:
            print(f"Campaign with ID {campaign_id} not found.")
            return
        
        old_status = campaign.status
        campaign.status = new_status
        db.session.commit()
        
        print(f"Campaign status changed from '{old_status}' to '{new_status}'")

def reschedule(args):
    """Reschedule a campaign to a new date/time"""
    campaign_id = args.id
    try:
        new_time = datetime.strptime(args.datetime, "%Y-%m-%d %H:%M")
    except ValueError:
        print("Invalid date format. Use YYYY-MM-DD HH:MM")
        return
    
    with app.app_context():
        campaign = EmailCampaign.query.get(campaign_id)
        
        if not campaign:
            print(f"Campaign with ID {campaign_id} not found.")
            return
        
        old_time = campaign.scheduled_time
        campaign.scheduled_time = new_time
        campaign.status = 'scheduled'
        db.session.commit()
        
        old_time_str = old_time.strftime('%Y-%m-%d %H:%M') if old_time else 'Not scheduled'
        print(f"Campaign rescheduled from '{old_time_str}' to '{new_time.strftime('%Y-%m-%d %H:%M')}'")
        print("Campaign status set to 'scheduled'")

def send_now(args):
    """Send a campaign immediately"""
    campaign_id = args.id
    
    with app.app_context():
        campaign = EmailCampaign.query.get(campaign_id)
        
        if not campaign:
            print(f"Campaign with ID {campaign_id} not found.")
            return
        
        print(f"Sending campaign '{campaign.name}' immediately...")
        
        # Set up the scheduler and service
        email_service = SESEmailService()
        scheduler = EmailScheduler(email_service)
        
        # Send the campaign
        try:
            scheduler.send_campaign(campaign)
            print("Campaign sent successfully!")
        except Exception as e:
            print(f"Error sending campaign: {str(e)}")

def delete_campaign(args):
    """Delete a campaign and its recipients"""
    campaign_id = args.id
    
    with app.app_context():
        campaign = EmailCampaign.query.get(campaign_id)
        
        if not campaign:
            print(f"Campaign with ID {campaign_id} not found.")
            return
        
        if not args.force:
            confirm = input(f"Are you sure you want to delete campaign '{campaign.name}'? This cannot be undone. (y/n): ")
            if confirm.lower() != 'y':
                print("Delete operation cancelled.")
                return
        
        # Delete recipients first
        recipients = EmailRecipient.query.filter_by(campaign_id=campaign.id).all()
        for recipient in recipients:
            db.session.delete(recipient)
        
        # Delete campaign
        db.session.delete(campaign)
        db.session.commit()
        
        print(f"Campaign '{campaign.name}' and {len(recipients)} recipients deleted successfully.")

def main():
    parser = argparse.ArgumentParser(description='Command-line tool for managing Bulk Email Scheduler')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # List campaigns
    list_parser = subparsers.add_parser('list', help='List all campaigns')
    list_parser.set_defaults(func=list_campaigns)
    
    # Show campaign details
    show_parser = subparsers.add_parser('show', help='Show campaign details')
    show_parser.add_argument('id', type=int, help='Campaign ID')
    show_parser.set_defaults(func=show_campaign)
    
    # Change campaign status
    status_parser = subparsers.add_parser('status', help='Change campaign status')
    status_parser.add_argument('id', type=int, help='Campaign ID')
    status_parser.add_argument('status', help='New status (draft, scheduled, in_progress, completed, failed)')
    status_parser.set_defaults(func=change_status)
    
    # Reschedule campaign
    reschedule_parser = subparsers.add_parser('reschedule', help='Reschedule a campaign')
    reschedule_parser.add_argument('id', type=int, help='Campaign ID')
    reschedule_parser.add_argument('datetime', help='New date and time (YYYY-MM-DD HH:MM)')
    reschedule_parser.set_defaults(func=reschedule)
    
    # Send campaign now
    send_parser = subparsers.add_parser('send', help='Send a campaign immediately')
    send_parser.add_argument('id', type=int, help='Campaign ID')
    send_parser.set_defaults(func=send_now)
    
    # Delete campaign
    delete_parser = subparsers.add_parser('delete', help='Delete a campaign')
    delete_parser.add_argument('id', type=int, help='Campaign ID')
    delete_parser.add_argument('--force', action='store_true', help='Skip confirmation prompt')
    delete_parser.set_defaults(func=delete_campaign)
    
    # Parse arguments
    args = parser.parse_args()
    
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
