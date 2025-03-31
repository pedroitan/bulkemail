"""
Email Campaign Scheduler Module

This module implements a background email scheduler using APScheduler with lazy initialization pattern.
The EmailScheduler only initializes the actual APScheduler instance when needed, preventing
issues with Flask application context and circular imports.
"""

import os
import re
import json
import pandas as pd
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, current_app
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from models import EmailCampaign, EmailRecipient, db
from email_service import SESEmailService
from werkzeug.utils import secure_filename

# Configure logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///campaigns.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = '/tmp'

db.init_app(app)

# Standalone function that can be serialized by APScheduler
def _run_campaign_job(campaign_id):
    """
    Execute the email campaign - standalone function for APScheduler
    
    This is defined at module level because APScheduler requires functions to be picklable.
    It creates a Flask application context before executing the campaign to ensure
    database access works correctly.
    
    Args:
        campaign_id: ID of the campaign to process
    """
    # Check if we're already in an app context
    from flask import current_app
    
    try:
        # Test if we're in app context already
        current_app._get_current_object()
        app = current_app
        in_context = True
    except RuntimeError:
        # Not in app context, create one
        from app import get_app
        app = get_app()
        in_context = False
    
    # Execute within app context if we're not already in one
    if not in_context:
        with app.app_context():
            return _execute_campaign(app, campaign_id)
    else:
        # Already in app context
        return _execute_campaign(app, campaign_id)

def _execute_campaign(app, campaign_id):
    """Internal function to execute the campaign within an app context"""
    try:
        # Get campaign details
        campaign = EmailCampaign.query.get(campaign_id)
        if not campaign:
            logging.error(f"Campaign {campaign_id} not found")
            return
        
        # Set campaign start time
        if not campaign.started_at:
            campaign.started_at = datetime.now()
            db.session.commit()
        
        # Log basic campaign info
        logging.info(f"Processing campaign {campaign_id}: {campaign.name} (status: {campaign.status})")
        
        # Update campaign status
        campaign.status = 'in_progress'
        db.session.commit()
        
        # Get recipients
        recipients = EmailRecipient.query.filter_by(campaign_id=campaign_id, status='pending').all()
        
        # Log recipient count and detailed info
        total_recipients = len(recipients)
        logging.info(f"Found {total_recipients} pending recipients for campaign {campaign_id}")
        
        # Count all recipients by status
        total_all = EmailRecipient.query.filter_by(campaign_id=campaign_id).count()
        pending = EmailRecipient.query.filter_by(campaign_id=campaign_id, status='pending').count()
        sent = EmailRecipient.query.filter_by(campaign_id=campaign_id, status='sent').count()
        failed = EmailRecipient.query.filter_by(campaign_id=campaign_id, status='failed').count()
        
        logging.info(f"Campaign {campaign_id} recipient breakdown - Total: {total_all}, Pending: {pending}, Sent: {sent}, Failed: {failed}")
        
        # Get email service
        email_service = app.get_email_service()
        
        # Process recipients in batches of 100
        batch_size = 100
        processed_count = 0
        batch_count = 0
        
        while processed_count < total_recipients:
            # Determine current batch end
            batch_end = min(processed_count + batch_size, total_recipients)
            current_batch = recipients[processed_count:batch_end]
            batch_count += 1
            
            logging.info(f"Processing batch {batch_count}: recipients {processed_count+1} to {batch_end} (batch size: {len(current_batch)})")
            
            # Process each recipient in the current batch
            for recipient in current_batch:
                try:
                    # Get recipient's custom data
                    custom_data = {}
                    if hasattr(recipient, 'custom_data') and recipient.custom_data:
                        custom_data = json.loads(recipient.custom_data)
                    
                    # Prepare template data with recipient info
                    template_data = {
                        'name': recipient.name or '',
                        'email': recipient.email,
                        **custom_data
                    }
                    
                    # Send email
                    message_id = email_service.send_template_email(
                        recipient=recipient.email,
                        subject=campaign.subject,
                        template_html=campaign.body_html,
                        template_text=campaign.body_text,
                        template_data=template_data,
                        sender_name=campaign.sender_name,
                        sender=campaign.sender_email  # Add the sender email from the campaign
                    )
                    
                    # Update recipient status
                    if message_id:
                        recipient.status = 'sent'
                        recipient.sent_at = datetime.now()
                        
                        # Store the message ID for bounce tracking
                        # AWS might return message IDs with angle brackets - remove them for consistent storage
                        if message_id.startswith('<') and message_id.endswith('>'):
                            message_id = message_id[1:-1]
                        
                        recipient.message_id = message_id
                        
                        # Initialize delivery_status to 'sent'
                        # This will be updated to 'delivered' by SNS notification handlers
                        recipient.delivery_status = 'sent'
                        
                        logging.info(f"Email sent to {recipient.email}, message ID: {message_id}")
                    else:
                        recipient.status = 'failed'
                        recipient.error_message = 'Failed to send email'
                        logging.error(f"Failed to send email to {recipient.email}: {recipient.error_message}")
                    
                    db.session.commit()
                    
                except Exception as e:
                    logging.error(f"Error sending to {recipient.email}: {str(e)}")
                    recipient.status = 'failed'
                    recipient.error_message = str(e)
                    db.session.commit()
            
            # Introduce a small delay between batches
            import time
            time.sleep(0.5)
            
            processed_count += batch_size
        
        # Update campaign status
        sent_count = EmailRecipient.query.filter_by(campaign_id=campaign_id, status='sent').count()
        failed_count = EmailRecipient.query.filter_by(campaign_id=campaign_id, status='failed').count()
        
        if failed_count > 0 and sent_count == 0:
            campaign.status = 'failed'
        elif failed_count > 0:
            campaign.status = 'completed_with_errors'
        else:
            campaign.status = 'completed'
        
        campaign.completed_at = datetime.now()
        db.session.commit()
        
        logging.info(f"Campaign {campaign_id} completed: {sent_count} sent, {failed_count} failed")
        
    except Exception as e:
        logging.error(f"Error running campaign {campaign_id}: {str(e)}")
        try:
            campaign = EmailCampaign.query.get(campaign_id)
            if campaign:
                campaign.status = 'failed'
                campaign.completed_at = datetime.now()
                db.session.commit()
        except Exception as inner_e:
            logging.error(f"Error updating campaign status: {str(inner_e)}")

class EmailScheduler:
    """
    Email Campaign Scheduler with lazy initialization pattern.
    
    This class manages scheduling and execution of email campaigns using APScheduler.
    It implements a lazy initialization pattern that only initializes the scheduler
    when it's actually needed, preventing issues with the Flask application context.
    
    Key features:
    - Delayed initialization until a scheduling operation is performed
    - Automatic re-initialization if scheduler stops
    - Handles both scheduled and immediate campaign execution
    - Supports rate limiting to prevent AWS throttling
    """
    
    def __init__(self, email_service=None):
        """
        Initialize the scheduler without starting it - implements lazy initialization pattern.
        
        Note: This constructor does NOT create the actual APScheduler instance. The scheduler
        is only initialized when needed via the init_scheduler() method.
        """
        self.email_service = email_service
        self.scheduler = None
        self.logger = logging.getLogger(__name__)
    
    def init_scheduler(self, app=None):
        """
        Initialize the scheduler with the application context - core lazy initialization method.
        
        This method implements the lazy initialization pattern by:
        1. Only creating the scheduler when it's actually needed
        2. Using the Flask application context to access configuration
        3. Setting up database connections for job persistence
        
        This pattern prevents the common Flask "RuntimeError: Working outside of application context"
        error that would occur if we initialized APScheduler at import time.
        
        Args:
            app: Optional Flask application instance. If not provided, uses current_app.
        """
        if self.scheduler and self.scheduler.running:
            return
            
        # Get database URI from app or current_app
        if app:
            db_uri = app.config['SQLALCHEMY_DATABASE_URI']
        else:
            db_uri = current_app.config['SQLALCHEMY_DATABASE_URI']
            
        # Configure job stores and executors
        jobstores = {
            'default': SQLAlchemyJobStore(url=db_uri)
        }
        executors = {
            'default': ThreadPoolExecutor(20)
        }
        
        # Create scheduler
        self.scheduler = BackgroundScheduler(jobstores=jobstores, executors=executors)
        
        # Start the scheduler
        self.scheduler.start()
        
        self.logger.info("Email scheduler initialized")
    
    def schedule_campaign(self, campaign_id, run_time):
        """
        Schedule an email campaign
        """
        if not self.scheduler or not self.scheduler.running:
            self.init_scheduler()
            
        job_id = f'campaign_{campaign_id}'
        
        # Check if job already exists and remove it
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
        
        # Add the new job using the standalone function
        self.scheduler.add_job(
            func=_run_campaign_job,  # Use standalone function instead of method
            trigger='date',
            run_date=run_time,
            id=job_id,
            args=[campaign_id],
            replace_existing=True
        )
        
        self.logger.info(f"Campaign {campaign_id} scheduled for {run_time}")
        
        return job_id
    
    def send_campaign(self, campaign):
        """Manually send a campaign immediately"""
        try:
            self.logger.info(f"Sending campaign {campaign.id} synchronously")
            
            # Run the campaign job directly instead of scheduling it
            # This will process the campaign synchronously
            result = _run_campaign_job(campaign.id)
            
            self.logger.info(f"Campaign {campaign.id} processed synchronously. Result: {result}")
            return f"Campaign {campaign.id} sent synchronously"
        except Exception as e:
            self.logger.error(f"Error sending campaign {campaign.id}: {str(e)}")
            raise
    
    def load_recipients_from_file(self, campaign_id, file_path):
        """
        Load recipients from a CSV or Excel file
        """
        try:
            # Determine file type and read accordingly
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path, header=None)  # No header row
            elif file_path.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file_path, header=None)  # No header row
            else:
                raise ValueError("Unsupported file format")
            
            # Rename the first column to 'email'
            df.columns = ['email']
            
            # Clean email addresses - remove commas and whitespace
            df['email'] = df['email'].astype(str).apply(lambda x: x.strip().rstrip(',').strip())
            
            # Remove any empty rows
            df = df[df['email'].str.len() > 0]
            
            # Process each row
            campaign = EmailCampaign.query.get(campaign_id)
            if not campaign:
                raise ValueError(f"Campaign {campaign_id} not found")
            
            # Delete existing recipients for this campaign
            EmailRecipient.query.filter_by(campaign_id=campaign_id).delete()
            
            # Add new recipients
            count = 0
            new_recipients = []
            for _, row in df.iterrows():
                email = row['email']
                
                # Skip empty emails
                if not email or pd.isna(email) or email.strip() == '':
                    continue
                
                # Create recipient record
                recipient = EmailRecipient(
                    campaign_id=campaign_id,
                    email=email,
                    name='',  # No name column in this case
                    status='pending'
                )
                
                new_recipients.append(recipient)
                count += 1
            
            # Add all recipients to the database
            db.session.bulk_save_objects(new_recipients)
            db.session.commit()
            
            return count
            
        except Exception as e:
            self.logger.error(f"Error loading recipients: {str(e)}")
            raise

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'csv', 'xlsx'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_email(email):
    # Basic email validation
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

@app.route('/campaigns/<int:campaign_id>')
def campaign_detail(campaign_id):
    campaign = EmailCampaign.query.get_or_404(campaign_id)
    recipients = EmailRecipient.query.filter_by(campaign_id=campaign_id).all()
    
    # Calculate recipient statistics
    total_recipients = len(recipients)
    recipient_stats = {
        'pending': len([r for r in recipients if r.status == 'pending']),
        'sent': len([r for r in recipients if r.status == 'sent']),
        'failed': len([r for r in recipients if r.status == 'failed'])
    }
    
    return render_template('campaign_detail.html', 
                         campaign=campaign, 
                         recipients=recipients,
                         total_recipients=total_recipients,
                         recipient_stats=recipient_stats)

@app.route('/campaigns/<int:campaign_id>/edit-recipients', methods=['GET', 'POST'])
def edit_campaign_recipients(campaign_id):
    campaign = EmailCampaign.query.get_or_404(campaign_id)
    recipients = EmailRecipient.query.filter_by(campaign_id=campaign_id).all()
    
    if request.method == 'POST':
        # Handle file upload
        if 'file' in request.files:
            file = request.files['file']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                
                try:
                    # Load recipients from file
                    scheduler = EmailScheduler()
                    scheduler.load_recipients_from_file(campaign_id, filepath)
                    flash('Recipients added successfully!', 'success')
                except Exception as e:
                    flash(f'Error loading recipients: {str(e)}', 'error')
                
                # Clean up the file
                os.remove(filepath)
            else:
                flash('Invalid file type. Please upload a CSV or Excel file.', 'error')
        
        # Handle manual email entry
        elif 'email' in request.form:
            email = request.form['email'].strip()
            if validate_email(email):
                recipient = EmailRecipient(
                    campaign_id=campaign_id,
                    email=email,
                    status='pending'
                )
                db.session.add(recipient)
                try:
                    db.session.commit()
                    flash('Recipient added successfully!', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Error adding recipient: {str(e)}', 'error')
            else:
                flash('Invalid email address.', 'error')
    
    return render_template('edit_recipients.html', campaign=campaign, recipients=recipients)

@app.route('/campaigns/<int:campaign_id>/recipient/<int:recipient_id>', methods=['POST'])
def delete_campaign_recipient(campaign_id, recipient_id):
    if request.form.get('_method') == 'DELETE':
        recipient = EmailRecipient.query.filter_by(id=recipient_id, campaign_id=campaign_id).first_or_404()
        try:
            db.session.delete(recipient)
            db.session.commit()
            flash('Recipient removed successfully', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error removing recipient: ' + str(e), 'error')
    
    return redirect(url_for('edit_campaign_recipients', campaign_id=campaign_id))
