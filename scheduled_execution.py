"""
Scheduled Execution Module for Bulk Email Scheduler

This module provides functionality for splitting large email campaigns into 
manageable batches and scheduling their execution on Render using cron jobs.
"""

import os
import json
import logging
import subprocess
from datetime import datetime, timedelta
from flask import Flask, flash, redirect, url_for, render_template, request
import requests

from models import EmailCampaign, EmailRecipient, BatchExecutionRecord, db
from session_manager import SessionManager

logger = logging.getLogger(__name__)

class ScheduledExecutionManager:
    """Manager for scheduled batch execution on Render."""
    
    def __init__(self, app=None):
        self.app = app
        # SessionManager uses static methods, no initialization needed
    
    def schedule_campaign(self, campaign_id, batch_size=1000, interval_minutes=5, start_time=None):
        """
        Schedule a campaign for batch execution.
        
        Args:
            campaign_id (int): The ID of the campaign to schedule
            batch_size (int): Number of emails per batch
            interval_minutes (int): Minutes between batch executions
            start_time (datetime): When to start execution (defaults to now)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get fresh campaign object using SessionManager static method
            campaign = SessionManager.get_fresh_object(EmailCampaign, campaign_id)
            if not campaign:
                logger.error(f"Campaign {campaign_id} not found")
                return False
                
            # Count recipients
            recipient_count = db.session.query(EmailRecipient).filter_by(
                campaign_id=campaign_id
            ).count()
            
            if recipient_count == 0:
                logger.warning(f"No recipients found for campaign {campaign_id}")
                return False
                
            # Calculate number of batches
            num_batches = (recipient_count + batch_size - 1) // batch_size
            
            # Set up campaign for batch execution
            campaign.batch_execution_enabled = True
            campaign.batch_size = batch_size
            campaign.batch_interval_minutes = interval_minutes
            campaign.total_batches = num_batches
            campaign.processed_batches = 0
            
            if start_time:
                campaign.scheduled_time = start_time
            else:
                campaign.scheduled_time = datetime.utcnow() + timedelta(minutes=1)
                
            # Create batch records
            for i in range(num_batches):
                start_index = i * batch_size
                record = BatchExecutionRecord(
                    campaign_id=campaign_id,
                    batch_number=i + 1,
                    start_index=start_index,
                    batch_size=batch_size,
                    status='pending',
                    scheduled_time=campaign.scheduled_time + timedelta(minutes=i * interval_minutes)
                )
                db.session.add(record)
            
            # Update campaign status
            campaign.status = 'scheduled'
            SessionManager.safely_commit()
            
            logger.info(f"Campaign {campaign_id} scheduled for batch execution: {num_batches} batches, {batch_size} emails per batch")
            
            # Set up render job if possible
            try:
                self._setup_render_job(campaign_id, batch_size)
            except Exception as e:
                logger.warning(f"Failed to set up Render job: {str(e)}")
                # This is non-critical - the user can still set up jobs manually
                
            return True
                
        except Exception as e:
            logger.error(f"Error scheduling campaign {campaign_id}: {str(e)}")
            return False
    
    def get_next_pending_batch(self, campaign_id):
        """Get the next pending batch for a campaign."""
        try:
            # Reset session to get fresh data
            db.session.expire_all()
            
            # Find the oldest pending batch for this campaign
            batch = BatchExecutionRecord.query.filter_by(
                campaign_id=campaign_id,
                status='pending'
            ).order_by(BatchExecutionRecord.scheduled_time).first()
            
            return batch
            
        except Exception as e:
            logger.error(f"Error getting next pending batch: {str(e)}")
            SessionManager.reset_session()
            return None
    
    def process_next_batch(self, campaign_id):
        """Process the next pending batch for a campaign."""
        batch = self.get_next_pending_batch(campaign_id)
        if not batch:
            logger.info(f"No pending batches for campaign {campaign_id}")
            return False
        
        # Get a fresh batch object to ensure it's bound to the current session    
        batch = SessionManager.get_fresh_object(BatchExecutionRecord, batch.id)
        if not batch:
            logger.error(f"Could not get fresh batch object for campaign {campaign_id}")
            return False
            
        # Run the command using Flask CLI
        command = [
            "flask", "process_email_batch", 
            str(campaign_id), 
            "--batch-size", str(batch.batch_size),
            "--start-index", str(batch.start_index)
        ]
        
        try:
            # Mark batch as in progress
            batch.status = 'in_progress'
            batch.started_at = datetime.utcnow()
            SessionManager.safely_commit()
            
            # Run command in background
            subprocess.Popen(command)
            logger.info(f"Started processing batch {batch.batch_number} for campaign {campaign_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing batch {batch.batch_number}: {str(e)}")
            batch.status = 'failed'
            batch.error = str(e)
            # Try to commit the status change
            try:
                SessionManager.safely_commit()
            except Exception:
                logger.error("Failed to update batch status after error")
            return False
    
    def update_batch_status(self, batch_id, status, processed=0, failed=0):
        """Update the status of a batch execution record."""
        try:
            # Get fresh objects using SessionManager to avoid session binding issues
            batch = SessionManager.get_fresh_object(BatchExecutionRecord, batch_id)
            if not batch:
                logger.error(f"Batch {batch_id} not found")
                return False
                
            batch.status = status
            batch.processed_count = processed
            batch.failed_count = failed
            
            if status in ['completed', 'failed']:
                batch.completed_at = datetime.utcnow()
                
                # Update campaign processed batches count
                campaign = SessionManager.get_fresh_object(EmailCampaign, batch.campaign_id)
                if campaign:
                    campaign.processed_batches += 1
                    
                    # If all batches processed, mark campaign as completed
                    if campaign.processed_batches >= campaign.total_batches:
                        campaign.status = 'completed'
                        campaign.completed_at = datetime.utcnow()
                        
            SessionManager.safely_commit()
            return True
            
        except Exception as e:
            logger.error(f"Error updating batch status: {str(e)}")
            return False
    
    def _setup_render_job(self, campaign_id, batch_size=1000):
        """
        Try to set up a Render job for the campaign.
        
        This uses the Render API to create a new job or modify
        an existing template job. This requires proper authentication
        with the Render API, which may not be available in all environments.
        """
        # This would require Render API credentials and configuration
        # For now, just document the process in the logs
        logger.info(f"To process campaign {campaign_id} with Render scheduled jobs:")
        logger.info(f"1. Go to your Render dashboard: https://dashboard.render.com")
        logger.info(f"2. Open your 'emailbulk-job-processor' cron service")
        logger.info(f"3. Edit the job command to replace __CAMPAIGN_ID__ with {campaign_id}")
        logger.info(f"4. Set the batch size to {batch_size}")
        logger.info(f"5. Enable the job and set its schedule")
        
        return True

def register_routes(app):
    """Register scheduled execution routes with the Flask application."""
    
    manager = ScheduledExecutionManager(app)
    
    @app.route('/campaigns/<int:campaign_id>/schedule', methods=['GET', 'POST'])
    def schedule_campaign_execution(campaign_id):
        """Schedule a campaign for batch execution."""
        campaign = EmailCampaign.query.get_or_404(campaign_id)
        
        # Count recipients
        recipient_count = EmailRecipient.query.filter_by(campaign_id=campaign_id).count()
        
        if request.method == 'POST':
            batch_size = int(request.form.get('batch_size', 1000))
            interval_minutes = int(request.form.get('interval_minutes', 5))
            scheduled_time = datetime.fromisoformat(request.form.get('scheduled_time').replace('Z', '+00:00'))
            use_scheduled_execution = request.form.get('use_scheduled_execution') == 'on'
            
            if use_scheduled_execution:
                # Schedule using the batch execution manager
                success = manager.schedule_campaign(
                    campaign_id=campaign_id,
                    batch_size=batch_size,
                    interval_minutes=interval_minutes,
                    start_time=scheduled_time
                )
                
                if success:
                    flash(f'Campaign scheduled for batch execution! It will be processed in {(recipient_count + batch_size - 1) // batch_size} batches.', 'success')
                else:
                    flash('Failed to schedule campaign for batch execution.', 'danger')
                    
            else:
                # Use traditional scheduling (direct APScheduler)
                campaign.scheduled_time = scheduled_time
                campaign.status = 'scheduled'
                db.session.commit()
                
                flash(f'Campaign scheduled for standard execution at {scheduled_time.strftime("%Y-%m-%d %H:%M")}', 'info')
                
            return redirect(url_for('campaign_detail', campaign_id=campaign_id))
                
        # GET request - show scheduling form
        now = datetime.utcnow()
        return render_template(
            'scheduled_campaign.html',
            campaign=campaign,
            recipient_count=recipient_count,
            now=now
        )
    
    @app.route('/campaigns/<int:campaign_id>/batches')
    def campaign_batch_status(campaign_id):
        """Show the status of batch execution for a campaign."""
        campaign = EmailCampaign.query.get_or_404(campaign_id)
        
        # Get all batches for this campaign
        batches = manager.get_batch_status(campaign_id)
        
        # Calculate overall statistics
        total_batches = len(batches)
        completed_batches = sum(1 for b in batches if b.status == 'completed')
        failed_batches = sum(1 for b in batches if b.status == 'failed')
        pending_batches = sum(1 for b in batches if b.status == 'pending')
        in_progress_batches = sum(1 for b in batches if b.status == 'in_progress')
        
        total_processed = sum(b.processed_count or 0 for b in batches)
        total_failed = sum(b.failed_count or 0 for b in batches)
        
        # Calculate overall progress percentage
        progress_pct = (completed_batches / total_batches * 100) if total_batches > 0 else 0
        
        return render_template(
            'campaign_batches.html',
            campaign=campaign,
            batches=batches,
            total_batches=total_batches,
            completed_batches=completed_batches,
            failed_batches=failed_batches,
            pending_batches=pending_batches,
            in_progress_batches=in_progress_batches,
            total_processed=total_processed,
            total_failed=total_failed,
            progress_pct=progress_pct
        )
    
    @app.route('/campaigns/<int:campaign_id>/process-next-batch')
    def manual_process_next_batch(campaign_id):
        """Manually process the next pending batch for a campaign."""
        campaign = EmailCampaign.query.get_or_404(campaign_id)
        
        if campaign.status not in ['scheduled', 'in_progress']:
            flash('Campaign is not scheduled or in progress.', 'warning')
            return redirect(url_for('campaign_batch_status', campaign_id=campaign_id))
        
        success = manager.process_next_batch(campaign_id)
        
        if success:
            flash('Started processing the next batch.', 'success')
        else:
            flash('No pending batches found or error occurred.', 'warning')
            
        return redirect(url_for('campaign_batch_status', campaign_id=campaign_id))
