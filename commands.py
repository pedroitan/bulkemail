import click
import os
from flask import current_app
from flask.cli import with_appcontext
from datetime import datetime, timedelta
import json

from models import EmailCampaign, EmailRecipient, db
from session_manager import SessionManager

@click.command('process_email_batch')
@click.argument('campaign_id', type=int)
@click.option('--batch-size', default=1000, help='Number of emails to process in this batch')
@click.option('--start-index', default=0, help='Starting index for this batch')
@with_appcontext
def process_email_batch(campaign_id, batch_size, start_index):
    """Process a batch of emails for a campaign.
    
    This command is designed to be run as a scheduled job in Render.
    It processes a subset of emails from a campaign, allowing for
    batch processing of large campaigns without timeout issues.
    """
    app = current_app
    session_manager = SessionManager(db.session)

    try:
        # Use SessionManager to get a fresh campaign object
        campaign = session_manager.get_object_by_id(EmailCampaign, campaign_id)
        if not campaign:
            click.echo(f"Campaign {campaign_id} not found")
            return
        
        # Check if campaign should be processed
        if campaign.status != 'scheduled' and campaign.status != 'in_progress':
            click.echo(f"Campaign {campaign_id} is not scheduled or in progress (status: {campaign.status})")
            return
        
        # Update campaign status if it's the first batch
        if start_index == 0 and campaign.status == 'scheduled':
            campaign.status = 'in_progress'
            campaign.started_at = datetime.utcnow()
            session_manager.commit()
            click.echo(f"Campaign {campaign_id} marked as in_progress")
        
        # Get recipients for this batch - using IDs only first to avoid session issues
        recipient_ids = db.session.query(EmailRecipient.id).filter_by(
            campaign_id=campaign_id,
            sent_status='pending'  # Only process pending emails
        ).offset(start_index).limit(batch_size).all()
        
        recipient_ids = [r[0] for r in recipient_ids]
        
        if not recipient_ids:
            # If no more recipients to process, check if campaign is complete
            pending_count = db.session.query(EmailRecipient).filter_by(
                campaign_id=campaign_id,
                sent_status='pending'
            ).count()
            
            if pending_count == 0 and campaign.status == 'in_progress':
                campaign.status = 'completed'
                campaign.completed_at = datetime.utcnow()
                session_manager.commit()
                click.echo(f"Campaign {campaign_id} marked as completed")
            else:
                click.echo(f"No more recipients to process in this batch. {pending_count} still pending.")
            return
        
        # Process this batch
        processed = 0
        failed = 0
        
        # Create a state file to track progress
        state_dir = os.path.join(app.instance_path, 'batch_states')
        os.makedirs(state_dir, exist_ok=True)
        state_file = os.path.join(state_dir, f'campaign_{campaign_id}_batch_{start_index}.json')
        
        with open(state_file, 'w') as f:
            json.dump({
                'campaign_id': campaign_id,
                'batch_size': batch_size,
                'start_index': start_index,
                'status': 'running',
                'started_at': datetime.utcnow().isoformat(),
                'recipient_count': len(recipient_ids)
            }, f)
        
        for recipient_id in recipient_ids:
            try:
                # Get a fresh recipient object for each email
                with session_manager.session_scope() as session:
                    recipient = session.query(EmailRecipient).get(recipient_id)
                    if not recipient:
                        continue
                    
                    # Here we would call the actual email sending logic
                    # Instead of using the background worker, we directly call the send method
                    from email_service import send_campaign_email
                    
                    result = send_campaign_email(
                        recipient=recipient,
                        campaign=campaign,
                        app=app
                    )
                    
                    # Update recipient status
                    recipient.sent_status = 'sent' if result.get('success') else 'failed'
                    recipient.sent_at = datetime.utcnow()
                    recipient.send_error = result.get('error')
                    
                    # Successfully sent
                    if result.get('success'):
                        processed += 1
                    else:
                        failed += 1
            except Exception as e:
                failed += 1
                click.echo(f"Error processing recipient {recipient_id}: {str(e)}")
        
        # Update the state file with results
        with open(state_file, 'w') as f:
            json.dump({
                'campaign_id': campaign_id,
                'batch_size': batch_size,
                'start_index': start_index,
                'status': 'completed',
                'started_at': datetime.utcnow().isoformat(),
                'completed_at': datetime.utcnow().isoformat(),
                'recipient_count': len(recipient_ids),
                'processed': processed,
                'failed': failed,
                'next_index': start_index + batch_size
            }, f)
        
        click.echo(f"Processed {processed} emails, {failed} failed")
        
        # Schedule next batch if needed
        if len(recipient_ids) == batch_size:
            click.echo(f"There may be more recipients to process. Next batch should start at index {start_index + batch_size}")
        
    except Exception as e:
        click.echo(f"Error processing batch: {str(e)}")
        # Update state file with error
        if 'state_file' in locals():
            with open(state_file, 'w') as f:
                json.dump({
                    'campaign_id': campaign_id,
                    'batch_size': batch_size,
                    'start_index': start_index,
                    'status': 'error',
                    'error': str(e),
                    'timestamp': datetime.utcnow().isoformat()
                }, f)

@click.command('check_campaign_progress')
@click.argument('campaign_id', type=int)
@with_appcontext
def check_campaign_progress(campaign_id):
    """Check the progress of a campaign's batch processing."""
    app = current_app
    
    campaign = EmailCampaign.query.get(campaign_id)
    if not campaign:
        click.echo(f"Campaign {campaign_id} not found")
        return
    
    # Get statistics
    total = EmailRecipient.query.filter_by(campaign_id=campaign_id).count()
    pending = EmailRecipient.query.filter_by(campaign_id=campaign_id, sent_status='pending').count()
    sent = EmailRecipient.query.filter_by(campaign_id=campaign_id, sent_status='sent').count()
    failed = EmailRecipient.query.filter_by(campaign_id=campaign_id, sent_status='failed').count()
    
    # Get batch state files
    state_dir = os.path.join(app.instance_path, 'batch_states')
    if os.path.exists(state_dir):
        batch_files = [f for f in os.listdir(state_dir) if f.startswith(f'campaign_{campaign_id}_batch_')]
        batch_states = []
        
        for batch_file in batch_files:
            file_path = os.path.join(state_dir, batch_file)
            try:
                with open(file_path, 'r') as f:
                    state = json.load(f)
                    batch_states.append(state)
            except Exception as e:
                click.echo(f"Error reading batch file {batch_file}: {str(e)}")
        
        click.echo(f"Campaign: {campaign.name} (ID: {campaign_id})")
        click.echo(f"Status: {campaign.status}")
        click.echo(f"Progress: {sent}/{total} sent ({pending} pending, {failed} failed)")
        click.echo(f"Batches processed: {len(batch_states)}")
        
        # Show detailed batch info
        for state in sorted(batch_states, key=lambda s: s.get('start_index', 0)):
            status = state.get('status', 'unknown')
            start_index = state.get('start_index', 0)
            processed = state.get('processed', 0)
            batch_failed = state.get('failed', 0)
            
            click.echo(f"  Batch starting at {start_index}: {status}, processed {processed}, failed {batch_failed}")
    else:
        click.echo(f"No batch state directory found")
        click.echo(f"Campaign: {campaign.name} (ID: {campaign_id})")
        click.echo(f"Status: {campaign.status}")
        click.echo(f"Progress: {sent}/{total} sent ({pending} pending, {failed} failed)")

@click.command('check_pending_campaigns')
@click.option('--process-next', is_flag=True, help='Process the next pending batch for each active campaign')
@with_appcontext
def check_pending_campaigns(process_next):
    """Check for pending campaign batches and process them if requested.
    
    This command is designed to be run as a scheduled job in Render.
    It looks for any campaigns with pending batches and processes the next batch
    for each campaign when the --process-next flag is set.
    """
    from scheduled_execution import ScheduledExecutionManager
    from models import EmailCampaign, BatchExecutionRecord
    
    # Initialize the manager
    execution_manager = ScheduledExecutionManager(current_app)
    
    # Find campaigns with pending batches
    pending_batches = BatchExecutionRecord.query.filter_by(status='pending').all()
    campaign_ids = set(batch.campaign_id for batch in pending_batches)
    
    if not campaign_ids:
        click.echo("No campaigns with pending batches found.")
        return
    
    click.echo(f"Found {len(campaign_ids)} campaigns with pending batches.")
    
    # Process next batch for each campaign if requested
    if process_next:
        for campaign_id in campaign_ids:
            # Get the campaign to check its status
            campaign = EmailCampaign.query.get(campaign_id)
            if not campaign:
                click.echo(f"Campaign {campaign_id} not found.")
                continue
                
            if campaign.status not in ['scheduled', 'in_progress']:
                click.echo(f"Campaign {campaign_id} is not active (status: {campaign.status}).")
                continue
                
            click.echo(f"Processing next batch for campaign {campaign_id}...")
            # Use the actual process_email_batch command for the next pending batch
            batch = execution_manager.get_next_pending_batch(campaign_id)
            if not batch:
                click.echo(f"No pending batches found for campaign {campaign_id}.")
                continue
                
            # Execute the process_email_batch command with the appropriate parameters
            ctx = click.Context(process_email_batch)
            ctx.ensure_object(dict)
            ctx.invoke(
                process_email_batch,
                campaign_id=campaign_id, 
                batch_size=batch.batch_size,
                start_index=batch.start_index
            )
            
            click.echo(f"Processed batch {batch.batch_number} for campaign {campaign_id}.")
    else:
        # Just list the pending batches for each campaign
        for campaign_id in campaign_ids:
            campaign_batches = BatchExecutionRecord.query.filter_by(
                campaign_id=campaign_id, 
                status='pending'
            ).order_by(BatchExecutionRecord.scheduled_time).all()
            
            click.echo(f"Campaign {campaign_id} has {len(campaign_batches)} pending batches:")
            for batch in campaign_batches:
                scheduled_time = batch.scheduled_time.strftime('%Y-%m-%d %H:%M:%S') if batch.scheduled_time else 'Not scheduled'
                click.echo(f"  Batch {batch.batch_number}: {scheduled_time}")

def register_commands(app):
    """Register custom CLI commands with the Flask application."""
    app.cli.add_command(process_email_batch)
    app.cli.add_command(check_campaign_progress)
    app.cli.add_command(check_pending_campaigns)
