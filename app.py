"""
Bulk Email Scheduler with Amazon SES

This is the main application file for the Bulk Email Scheduler, implementing a Flask web application
for creating, managing, and sending email campaigns through Amazon SES.

The application follows a lazy initialization pattern for components like the email service
and scheduler to prevent "working outside of application context" errors that are common
in Flask applications.
"""

from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, copy_current_request_context
import os
import io
import json
import csv
import time
import random
import string
import logging
import threading
import re
from datetime import datetime, timedelta
from models import db, EmailCampaign, EmailRecipient
from forms import CampaignForm, UploadRecipientsForm
from email_service import SESEmailService
import sqs_jobs  # Import the module containing SQS job functions
from scheduler import EmailScheduler
from utils import allowed_file, save_uploaded_file, preview_file_data, get_campaign_stats
from dotenv import load_dotenv
from email_tracking import init_tracking
from email_verification import EmailVerifier
from sqs_handler import SQSHandler
from recipient_lists import recipient_lists_bp
from aws_usage import aws_usage_blueprint, track_email_sent, track_sns_notification

# Load environment variables from .env file immediately
load_dotenv()

# Add rate limiter for SNS notifications
class TokenBucketRateLimiter:
    """
    A token bucket rate limiter that prevents server overload from SNS notifications.
    
    This is a critical component for handling large email campaigns where thousands
    of SNS notifications can arrive nearly simultaneously, overwhelming the server 
    and causing 502 Bad Gateway errors.
    
    The rate limiter implements a token bucket algorithm where:
    1. Tokens are consumed when processing notifications
    2. Tokens are replenished at a fixed rate over time
    3. When tokens are depleted, requests are rate-limited
    4. Critical notifications bypass the rate limiting (Bounces, Complaints)
    5. Non-critical notifications are aggressively filtered (99.5% drop rate)
    
    Without this rate limiter, large campaigns (up to 40k emails) would trigger 
    simultaneous notifications that would overwhelm the server on Render's free tier.
    """
    def __init__(self, max_tokens, refill_rate):
        self.max_tokens = max_tokens  # Maximum number of tokens in the bucket
        self.refill_rate = refill_rate  # Tokens refilled per second
        self.tokens = max_tokens  # Current token count
        self.last_refill_time = time.time()  # Last time tokens were refilled
        self.lock = threading.Lock()  # Lock for thread safety
    
    def consume(self, tokens=1, bypass=False):
        """
        Consume tokens from the bucket
        Returns True if tokens were consumed successfully, False otherwise
        bypass=True will skip rate limiting
        """
        if bypass:
            return True
            
        with self.lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    def _refill(self):
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill_time
        new_tokens = elapsed * self.refill_rate
        if new_tokens > 0:
            self.tokens = min(self.max_tokens, self.tokens + new_tokens)
            self.last_refill_time = now

# Initialize rate limiter with fewer tokens and slower refill rate to prevent 502 errors
# These values are further optimized for Render's free tier with large campaigns
sns_rate_limiter = TokenBucketRateLimiter(max_tokens=3, refill_rate=0.3)

def create_app(config_object='config.Config'):
    """
    Create and configure the Flask application.
    
    This function implements the application factory pattern combined with lazy initialization
    to ensure components are only initialized when they're actually needed within a proper
    Flask application context.
    
    Returns:
        Flask application instance
    """
    # Report errors to Sentry if available
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=os.environ.get('SENTRY_DSN'),
            traces_sample_rate=1.0
        )
    except (ImportError, Exception):
        pass
        
    # Setup logging with more detail
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Create a handler that writes to stdout
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    
    # Add the handler to the root logger
    logging.getLogger('').addHandler(console_handler)

    # Create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object)
    
    # Configure application from environment variables
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-dev-key')
    app.config['AWS_ACCESS_KEY_ID'] = os.environ.get('AWS_ACCESS_KEY_ID', '')
    app.config['AWS_SECRET_ACCESS_KEY'] = os.environ.get('AWS_SECRET_ACCESS_KEY', '')
    app.config['AWS_REGION'] = os.environ.get('AWS_REGION', 'us-east-1')
    app.config['SENDER_EMAIL'] = os.environ.get('SENDER_EMAIL', '')
    app.config['MAX_EMAILS_PER_SECOND'] = int(os.environ.get('MAX_EMAILS_PER_SECOND', 10))
    app.config['SQS_QUEUE_URL'] = os.environ.get('SQS_QUEUE_URL', '')
    app.config['SQS_ENABLED'] = os.environ.get('SQS_ENABLED', 'false').lower() == 'true'
    app.config['SQS_REGION'] = os.environ.get('SQS_REGION', app.config['AWS_REGION'])
    app.config['SNS_DIRECT_DISABLED'] = os.environ.get('SNS_DIRECT_DISABLED', 'false').lower() == 'true'
    
    # Set up SQLAlchemy database
    db_url = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
    
    # Fix for PostgreSQL SSL connections (especially on Render)
    if db_url.startswith('postgresql'):
        logging.info("PostgreSQL connection detected. Configuring SSL parameters.")
        
        # Create a proper connection URL with comprehensive SSL parameters
        from urllib.parse import urlparse, parse_qs, urlencode
        
        # Parse the existing URL
        parsed_url = urlparse(db_url)
        
        # Get existing query parameters if any
        query_params = parse_qs(parsed_url.query)
        
        # Set SSL parameters with fallbacks to defaults
        query_params['sslmode'] = ['prefer']  # Start with 'prefer' instead of 'require'
        
        # Build the query string
        query_string = urlencode(query_params, doseq=True)
        
        # Reconstruct the URL with updated query string
        db_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}?{query_string}"
        
        # Configure SQLAlchemy engine creation parameters
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'connect_args': {
                'options': '-c statement_timeout=60000'  # 60 seconds timeout
            },
            'pool_pre_ping': True,  # Health check the connection before using it
            'pool_recycle': 300,    # Recycle connections after 5 minutes
            'pool_timeout': 30      # Wait max 30 seconds for a connection
        }
        
        logging.info(f"Modified database URL with SSL parameters. Using sslmode=prefer")
    
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    
    # Initialize database
    db.init_app(app)
    
    # Register AWS usage dashboard blueprint
    app.register_blueprint(aws_usage_blueprint)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Initialize email service, scheduler, and SQS handler lazily
    email_service = None
    scheduler = None
    sqs_handler = None
    
    def get_email_service():
        """
        Get the email service instance, creating it only when needed.
        This implements lazy initialization to prevent Flask context errors.
        """
        nonlocal email_service
        if email_service is None:
            email_service = SESEmailService(
                aws_access_key_id=app.config['AWS_ACCESS_KEY_ID'],
                aws_secret_access_key=app.config['AWS_SECRET_ACCESS_KEY'],
                region_name=app.config['AWS_REGION']
            )
        return email_service
    
    def get_scheduler():
        """
        Get the email scheduler instance, creating it only when needed.
        This implements lazy initialization to prevent Flask context errors.
        """
        nonlocal scheduler
        if scheduler is None:
            scheduler = EmailScheduler(get_email_service())
            # Initialize scheduler with app
            with app.app_context():
                scheduler.init_scheduler(app)
        return scheduler
        
    def get_sqs_handler():
        """
        Get the SQS handler instance, creating it only when needed.
        This implements lazy initialization to prevent Flask context errors.
        """
        nonlocal sqs_handler
        if sqs_handler is None:
            sqs_handler = SQSHandler()
        return sqs_handler
    
    # Make these functions available to the application context
    app.get_email_service = get_email_service
    app.get_scheduler = get_scheduler
    app.get_sqs_handler = get_sqs_handler
    
    # Initialize email tracking system
    with app.app_context():
        tracking_manager = init_tracking(app, db)
        app.tracking_manager = tracking_manager
        
        # Connect tracking manager to the email service
        email_service = app.get_email_service()
        email_service.tracking_manager = tracking_manager
        app.logger.info("Connected tracking manager to email service")
    
    # Initialize email verifier
    app.email_verifier = EmailVerifier()
    
    # Register the recipient_lists blueprint
    app.register_blueprint(recipient_lists_bp)

    # Routes
    @app.route('/')
    def index():
        # Dashboard overview
        campaigns = EmailCampaign.query.order_by(EmailCampaign.created_at.desc()).all()
        # Calculate statistics for dashboard
        stats = {
            'total': len(campaigns),
            'scheduled': EmailCampaign.query.filter_by(status='scheduled').count(),
            'in_progress': EmailCampaign.query.filter_by(status='in_progress').count(),
            'completed': EmailCampaign.query.filter_by(status='completed').count(),
            'failed': EmailCampaign.query.filter_by(status='failed').count()
        }
        # Get recent campaigns for dashboard
        recent_campaigns = campaigns[:5] if campaigns else []
        return render_template('index.html', campaigns=recent_campaigns, stats=stats)
    
    @app.route('/campaigns')
    def campaigns():
        # List all campaigns
        campaigns = EmailCampaign.query.order_by(EmailCampaign.created_at.desc()).all()
        return render_template('campaigns.html', campaigns=campaigns)
    
    @app.route('/campaigns/create', methods=['GET', 'POST'])
    def create_campaign():
        form = CampaignForm()
        
        # Populate the sender domain dropdown with verified domains from config
        domains = app.config.get('SENDER_DOMAINS', [])
        if domains:
            form.sender_domain.choices = [(domain, domain) for domain in domains if domain]
            
            # Set vendo147.com as the default domain if it exists in choices
            if not form.is_submitted() and 'vendo147.com' in [choice[0] for choice in form.sender_domain.choices]:
                form.sender_domain.data = 'vendo147.com'
        
        # Pre-populate sender email field with username part of the default sender email
        default_email = app.config.get('SENDER_EMAIL')
        if default_email and '@' in default_email:
            username, domain = default_email.split('@', 1)
            if not form.is_submitted():
                form.sender_email.data = username
            
            # Select the domain in the dropdown if it exists in choices
            if domain in [choice[0] for choice in form.sender_domain.choices]:
                form.sender_domain.data = domain
        
        if form.validate_on_submit():
            # Combine the sender email username and domain
            full_sender_email = f"{form.sender_email.data}@{form.sender_domain.data}"
            
            # Create new campaign
            campaign = EmailCampaign(
                name=form.name.data,
                subject=form.subject.data,
                body_html=form.body_html.data,
                body_text=form.body_text.data,
                sender_name=form.sender_name.data,
                sender_email=full_sender_email,  # Store the full sender email
                scheduled_time=form.scheduled_time.data,
                status='scheduled' if form.scheduled_time.data else 'draft'
            )
            db.session.add(campaign)
            db.session.commit()
            
            # Schedule the campaign if a time is set
            if form.scheduled_time.data and form.scheduled_time.data > datetime.now():
                app.get_scheduler().schedule_campaign(campaign.id, campaign.scheduled_time)
                flash('Campaign scheduled successfully!', 'success')
            else:
                flash('Campaign created as draft!', 'success')
            
            return redirect(url_for('upload_recipients', campaign_id=campaign.id))
        
        return render_template('create_campaign.html', form=form)
    
    @app.route('/campaigns/<int:campaign_id>/edit', methods=['GET', 'POST'])
    def edit_campaign(campaign_id):
        campaign = EmailCampaign.query.get_or_404(campaign_id)
        form = CampaignForm(obj=campaign)
        
        # Populate the sender domain dropdown with verified domains from config
        domains = app.config.get('SENDER_DOMAINS', [])
        if domains:
            form.sender_domain.choices = [(domain, domain) for domain in domains if domain]
            
            # If this is a new form load (not a submission) and no sender email exists
            if not form.is_submitted() and (not campaign.sender_email or '@' not in campaign.sender_email):
                # Set vendo147.com as the default domain
                if 'vendo147.com' in [choice[0] for choice in form.sender_domain.choices]:
                    form.sender_domain.data = 'vendo147.com'
        
        # Split the sender email into username and domain if it's in the campaign
        if campaign.sender_email and '@' in campaign.sender_email and not form.is_submitted():
            username, domain = campaign.sender_email.split('@', 1)
            form.sender_email.data = username
            if domain in [choice[0] for choice in form.sender_domain.choices]:
                form.sender_domain.data = domain
        
        if form.validate_on_submit():
            old_scheduled_time = campaign.scheduled_time
            
            # Update basic campaign fields
            form.populate_obj(campaign)
            
            # Combine the sender email username and domain
            campaign.sender_email = f"{form.sender_email.data}@{form.sender_domain.data}"
            
            # Update status based on scheduled time
            if campaign.scheduled_time and campaign.scheduled_time > datetime.now():
                campaign.status = 'scheduled'
            elif not campaign.scheduled_time:
                # Reset status to draft even if it was previously completed
                campaign.status = 'draft'
            
            db.session.commit()
            flash('Campaign updated successfully', 'success')
            
            return redirect(url_for('campaign_detail', campaign_id=campaign.id))
        
        return render_template('edit_campaign.html', form=form, campaign=campaign)
    
    @app.route('/campaigns/<int:campaign_id>/delete', methods=['POST', 'DELETE'])
    def delete_campaign(campaign_id):
        """Delete a campaign"""
        try:
            campaign = EmailCampaign.query.get_or_404(campaign_id)
            
            # Delete all recipients associated with the campaign
            EmailRecipient.query.filter_by(campaign_id=campaign_id).delete()
            
            # Delete the campaign
            db.session.delete(campaign)
            db.session.commit()
            
            # Add flash message
            flash('Campaign deleted successfully', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error deleting campaign: {str(e)}', 'danger')
        
        # Always redirect to campaigns list
        return redirect(url_for('campaigns'))
    
    @app.route('/campaigns/<int:campaign_id>/delete-redirect', methods=['POST'])
    def delete_campaign_with_redirect(campaign_id):
        """Delete a campaign and redirect to campaigns list page"""
        try:
            campaign = EmailCampaign.query.get_or_404(campaign_id)
            
            # Delete all recipients associated with the campaign
            EmailRecipient.query.filter_by(campaign_id=campaign_id).delete()
            
            # Delete the campaign
            db.session.delete(campaign)
            db.session.commit()
            
            flash('Campaign deleted successfully', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error deleting campaign: {str(e)}', 'danger')
        
        # Always redirect back to campaigns list
        return redirect(url_for('campaigns'))
    
    @app.route('/campaigns/<int:campaign_id>/delete-direct', methods=['POST'])
    def delete_campaign_direct(campaign_id):
        """Delete a campaign and redirect directly (no JSON)"""
        try:
            campaign = EmailCampaign.query.get_or_404(campaign_id)
            
            # Delete all recipients associated with the campaign
            EmailRecipient.query.filter_by(campaign_id=campaign_id).delete()
            
            # Delete the campaign
            db.session.delete(campaign)
            db.session.commit()
            
            flash('Campaign deleted successfully', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error deleting campaign: {str(e)}', 'danger')
        
        # Always redirect back to campaigns list
        return redirect(url_for('campaigns'))
    
    @app.route('/campaigns/<int:campaign_id>/start', methods=['POST'])
    def start_campaign(campaign_id):
        """Immediately start sending a campaign"""
        app.logger.info(f"START CAMPAIGN ENDPOINT CALLED for campaign_id={campaign_id}")
        try:
            campaign = EmailCampaign.query.get_or_404(campaign_id)
            
            # Allow starting campaigns regardless of their status
            # Just log a warning for non-standard states
            if campaign.status not in ['draft', 'scheduled']:
                app.logger.warning(f"Starting campaign with non-standard status: {campaign.status}")
            
            # Update campaign status to in_progress
            campaign.status = 'in_progress'
            db.session.commit()
            
            # Get the scheduler and send the campaign
            scheduler = app.get_scheduler()
            result = scheduler.send_campaign(campaign)
            app.logger.info(f"Campaign {campaign_id} send result: {result}")
            
            return jsonify({'success': True, 'message': "Campaign sending started"})
        except Exception as e:
            app.logger.error(f"Error starting campaign: {str(e)}")
            return jsonify({'success': False, 'message': f"Error: {str(e)}"})
    
    @app.route('/campaigns/<int:campaign_id>/reset', methods=['POST'])
    def reset_campaign(campaign_id):
        """Reset a campaign to draft status so it can be edited and sent again"""
        try:
            campaign = EmailCampaign.query.get_or_404(campaign_id)
            
            # Clear existing job schedules for this campaign
            scheduler = app.get_scheduler()
            if hasattr(scheduler, 'remove_job'):
                scheduler.remove_job(f'campaign_{campaign_id}')
            
            # Reset all recipients to pending status
            recipient_count = EmailRecipient.query.filter_by(campaign_id=campaign_id).count()
            updated = EmailRecipient.query.filter_by(campaign_id=campaign_id).update(
                {'status': 'pending', 'sent_at': None, 'error_message': None}
            )
            
            # Reset campaign status
            campaign.status = 'draft'
            campaign.started_at = None
            campaign.completed_at = None
            
            db.session.commit()
            
            app.logger.info(f"Reset campaign {campaign_id}: {updated} recipients reset out of {recipient_count}")
            
            flash(f'Campaign has been reset: {updated} recipients returned to pending status', 'success')
            return redirect(url_for('campaign_detail', campaign_id=campaign_id))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error resetting campaign {campaign_id}: {str(e)}")
            flash(f'Error resetting campaign: {str(e)}', 'danger')
            return redirect(url_for('campaign_detail', campaign_id=campaign_id))
    
    @app.route('/campaigns/<int:campaign_id>/upload', methods=['GET', 'POST'])
    def upload_recipients(campaign_id):
        campaign = EmailCampaign.query.get_or_404(campaign_id)
        form = UploadRecipientsForm()
        
        # Get all recipient lists for selection with error handling
        try:
            recipient_lists = RecipientList.query.order_by(RecipientList.name).all()
        except Exception as e:
            app.logger.error(f"Error fetching recipient lists: {str(e)}")
            recipient_lists = []  # Provide empty list as fallback
        
        # Handle list selection
        list_id = request.args.get('list_id') or request.form.get('list_id')
        if list_id:
            # Selected from an existing recipient list
            recipient_list = RecipientList.query.get_or_404(list_id)
            
            # Get recipients from the list, excluding problematic ones
            recipients = EmailRecipient.query.join(
                recipient_list_items,
                (recipient_list_items.c.recipient_id == EmailRecipient.id) & 
                (recipient_list_items.c.list_id == list_id)
            ).filter(EmailRecipient.global_status == 'active').all()
            
            # Add recipients to the campaign
            added_count = 0
            for recipient in recipients:
                # Create a new campaign-specific recipient record
                campaign_recipient = EmailRecipient(
                    campaign_id=campaign.id,
                    email=recipient.email,
                    name=recipient.name,
                    status='pending',
                    global_status=recipient.global_status,
                    custom_data=recipient.custom_data
                )
                db.session.add(campaign_recipient)
                added_count += 1
                
            db.session.commit()
            flash(f'Successfully added {added_count} recipients from list "{recipient_list.name}"!', 'success')
            return redirect(url_for('campaign_detail', campaign_id=campaign_id))
        
        # Handle file upload
        if form.validate_on_submit():
            file = form.file.data
            if file and allowed_file(file.filename):
                file_path = save_uploaded_file(file)
                
                # Save the file path
                campaign.recipients_file = file_path
                db.session.commit()
                
                # Preview data
                preview = preview_file_data(file_path)
                
                # If user wants to save this as a recipient list
                if form.save_as_list.data:
                    list_name = form.list_name.data or f"List from {campaign.name}"
                    save_for_future = form.save_as_list.data
                    
                    return render_template(
                        'confirm_recipients.html',
                        campaign=campaign,
                        preview=preview,
                        file_path=file_path,
                        save_as_list=save_for_future,
                        list_name=list_name
                    )
                else:
                    return render_template(
                        'confirm_recipients.html',
                        campaign=campaign,
                        preview=preview,
                        file_path=file_path
                    )
            else:
                flash('Invalid file format. Please upload a CSV or Excel file.', 'danger')
        
        # Always ensure recipient_lists is passed, even if it might be empty
        return render_template('upload_recipients.html', form=form, campaign=campaign, recipient_lists=recipient_lists)
    
    @app.route('/campaigns/<int:campaign_id>/confirm-recipients', methods=['POST'])
    def confirm_recipients(campaign_id):
        campaign = EmailCampaign.query.get_or_404(campaign_id)
        file_path = request.form.get('file_path')
        save_as_list = request.form.get('save_as_list') == 'True'
        list_name = request.form.get('list_name')
        
        try:
            # Load recipients from file, filtering out problematic recipients
            count = app.get_scheduler().load_recipients_from_file(campaign_id, file_path)
            
            # Save as a recipient list if requested
            if save_as_list and list_name:
                new_list = RecipientList(name=list_name, description=f"Created from campaign '{campaign.name}'")
                db.session.add(new_list)
                db.session.flush()  # Get the new list ID
                
                # Associate recipients with the list
                recipients = EmailRecipient.query.filter_by(campaign_id=campaign_id).all()
                for recipient in recipients:
                    stmt = recipient_list_items.insert().values(
                        list_id=new_list.id,
                        recipient_id=recipient.id
                    )
                    db.session.execute(stmt)
                
                # Update list stats
                new_list.update_stats()
                db.session.commit()
                
                flash(f'Successfully loaded {count} recipients and saved as list "{list_name}"!', 'success')
            else:
                flash(f'Successfully loaded {count} recipients!', 'success')
                
            return redirect(url_for('campaign_detail', campaign_id=campaign_id))
        except Exception as e:
            flash(f'Error loading recipients: {str(e)}', 'danger')
            return redirect(url_for('upload_recipients', campaign_id=campaign_id))
    
    @app.route('/campaigns/<int:campaign_id>')
    def campaign_detail(campaign_id):
        campaign = EmailCampaign.query.get_or_404(campaign_id)
        recipients = EmailRecipient.query.filter_by(campaign_id=campaign_id).limit(10).all()
        
        # Calculate status stats for pie chart
        status_counts = db.session.query(
            EmailRecipient.status, 
            db.func.count(EmailRecipient.id)
        ).filter_by(campaign_id=campaign_id).group_by(EmailRecipient.status).all()
        
        status_stats = {
            'pending': 0,
            'sent': 0,
            'failed': 0
        }
        
        for status, count in status_counts:
            if status in status_stats:
                status_stats[status] = count
        
        # Calculate delivery status stats
        delivery_counts = db.session.query(
            EmailRecipient.delivery_status, 
            db.func.count(EmailRecipient.id)
        ).filter_by(campaign_id=campaign_id).group_by(EmailRecipient.delivery_status).all()
        
        delivery_stats = {
            'sent': 0,
            'delivered': 0,
            'bounced': 0,
            'complained': 0,
            'unknown': 0
        }
        
        for status, count in delivery_counts:
            if status in delivery_stats:
                delivery_stats[status] = count
            else:
                delivery_stats['unknown'] += count
        
        # Calculate bounce type stats
        bounce_counts = db.session.query(
            EmailRecipient.bounce_type, 
            db.func.count(EmailRecipient.id)
        ).filter_by(campaign_id=campaign_id).filter(EmailRecipient.bounce_type.isnot(None)).group_by(EmailRecipient.bounce_type).all()
        
        bounce_stats = {}
        for bounce_type, count in bounce_counts:
            bounce_stats[bounce_type] = count
        
        return render_template(
            'campaign_detail.html', 
            campaign=campaign, 
            recipients=recipients,
            recipient_stats=status_stats,
            delivery_stats=delivery_stats,
            bounce_stats=bounce_stats
        )
    
    @app.route('/campaigns/<int:campaign_id>/view-recipients')
    def view_campaign_recipients(campaign_id):
        campaign = EmailCampaign.query.get_or_404(campaign_id)
        
        # Pagination
        page = request.args.get('page', 1, type=int)
        per_page = 50
        
        recipients = EmailRecipient.query.filter_by(campaign_id=campaign_id).paginate(
            page=page, per_page=per_page
        )
        
        return render_template(
            'campaign_recipients.html',
            campaign=campaign,
            recipients=recipients
        )
    
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
                        name='Manual Entry',
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
    
    @app.route('/campaigns/<int:campaign_id>/recipients/<int:recipient_id>/delete', methods=['POST'])
    def delete_campaign_recipient(campaign_id, recipient_id):
        try:
            recipient = EmailRecipient.query.get_or_404(recipient_id)
            if recipient.campaign_id != campaign_id:
                flash('Invalid recipient for this campaign', 'error')
                return redirect(url_for('edit_campaign_recipients', campaign_id=campaign_id))
            
            db.session.delete(recipient)
            db.session.commit()
            flash('Recipient deleted successfully', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error deleting recipient: {str(e)}', 'error')
        
        return redirect(url_for('edit_campaign_recipients', campaign_id=campaign_id))
    
    @app.route('/campaigns/<int:campaign_id>/test', methods=['POST'])
    def send_test_email(campaign_id):
        campaign = EmailCampaign.query.get_or_404(campaign_id)
        email = request.form.get('email')
        
        if not email:
            return jsonify({'success': False, 'message': 'Email address is required'})
        
        # Send test email
        email_service = app.get_email_service()
        try:
            result = email_service.send_email(
                recipient=email,
                subject=f"[TEST] {campaign.subject}",
                body_html=campaign.body_html,
                body_text=campaign.body_text,
                sender_name=campaign.sender_name
            )
            
            return jsonify({
                'success': result['success'],
                'message': 'Test email sent successfully!' if result['success'] else result.get('error', 'Failed to send test email')
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error sending test email: {str(e)}'
            })
    
    @app.route('/api/campaigns/<int:campaign_id>/status', methods=['GET'])
    def get_campaign_status(campaign_id):
        """Get the current status of a campaign for status polling"""
        try:
            campaign = EmailCampaign.query.get_or_404(campaign_id)
            
            # Format the status for display
            status_display = campaign.status.replace('_', ' ').title()
            
            return jsonify({
                'success': True,
                'status': campaign.status,
                'status_display': status_display
            })
        except Exception as e:
            app.logger.error(f"Error getting campaign status: {str(e)}")
            return jsonify({
                'success': False,
                'status': 'error',
                'status_display': 'Error',
                'message': str(e)
            })
    
    @app.route('/campaigns/<int:campaign_id>/add-test-recipients', methods=['POST'])
    def add_test_recipients(campaign_id):
        """Add test recipients to a campaign for testing"""
        try:
            campaign = EmailCampaign.query.get_or_404(campaign_id)
            
            # Add a test recipient
            test_recipient = EmailRecipient(
                campaign_id=campaign_id,
                email='pedroitan@gmail.com',
                name='Pedro Itan',
                status='pending'
            )
            
            db.session.add(test_recipient)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Test recipient added successfully!'
            })
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error adding test recipient: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'Error adding test recipient: {str(e)}'
            })
    
    @app.route('/api/sns/ses-notification', methods=['POST'])
    def sns_notification_handler():
        # Check if SNS notifications are globally disabled
        if os.environ.get('DISABLE_SNS_NOTIFICATIONS', 'false').lower() == 'true':
            app.logger.warning("⚠️ SNS notifications are disabled. Returning OK to prevent retries.")
            return jsonify({
                'success': True,
                'message': 'SNS notifications are globally disabled'
            }), 200
            
        # Track SNS notification for AWS usage metrics
        try:
            track_sns_notification()
        except Exception as e:
            app.logger.error(f"Error tracking SNS notification: {str(e)}")
            
        # Add detailed debugging for SES-SNS-SQS notification flow
        app.logger.debug("==== RECEIVED SNS NOTIFICATION ====")
        app.logger.debug(f"Headers: {request.headers}")
        
        # Debug the raw data with safety measures for large payloads
        raw_data = request.data.decode('utf-8')
        app.logger.debug(f"Raw data length: {len(raw_data)} bytes")
        if len(raw_data) > 2000:
            app.logger.debug(f"Raw data (truncated): {raw_data[:1000]}...{raw_data[-1000:]}")
        else:
            app.logger.debug(f"Raw data: {raw_data}")
            
        # If SNS_DIRECT_DISABLED is true, immediately return success
        # This prevents direct SNS notifications from affecting the app while still allowing SQS processing
        if app.config.get('SNS_DIRECT_DISABLED', False):
            app.logger.debug("Direct SNS notifications are disabled, returning early")
            return jsonify({
                'success': True, 
                'message': 'Direct SNS notifications are disabled, notifications are processed via SQS'
            }), 200
        """
        Handle AWS SNS notifications for email bounces, complaints, and deliveries.
        
        This is a critical endpoint for tracking email status but can be overwhelmed
        during large campaigns (up to 40k emails) when thousands of notifications arrive
        simultaneously. Key optimizations include:
        
        1. SQS Queue Integration: When enabled, forwards notifications to an SQS queue
           for asynchronous processing at a controlled rate, preserving all notification data
        
        2. Rate Limiting: Uses a token bucket algorithm to process at most 5 
           notifications per second with a 0.5/sec refill rate, preventing server overload
        
        3. Priority Handling: Critical notifications (bounces, complaints) bypass 
           rate limiting to ensure delivery issues are always tracked
        
        4. Aggressive Filtering: Filters 99.5% of all non-critical notifications
           (not just Send events) to drastically reduce server load when SQS is disabled
        
        5. 200 OK Responses: Always returns HTTP 200 even for rate-limited requests 
           to prevent AWS from retrying, which would worsen server load
        
        6. Error Tolerance: Catches and handles parsing errors gracefully to prevent
           notification processing failures
        
        These optimizations allow the system to handle extremely large campaigns (up to 40k emails)
        without experiencing 502 Bad Gateway errors that would otherwise occur when the server
        is overwhelmed by simultaneous SNS notifications on Render's free tier.
        """
        try:
            # Enhanced logging
            app.logger.info("======= SNS NOTIFICATION RECEIVED =======")
            app.logger.info(f"Headers: {dict(request.headers)}")
            
            # Safely get raw data
            try:
                raw_data = request.data.decode('utf-8')
                app.logger.info(f"Raw Data: {raw_data[:500]}...")  # Log first 500 chars
            except Exception as e:
                app.logger.error(f"Error decoding request data: {str(e)}")
                raw_data = str(request.data)
            
            # Get the content of the request - handle different content types with more robust error handling
            app.logger.info(f"Received SNS notification with Content-Type: {request.content_type}")
            
            # Simple endpoint health check - respond with 200 OK regardless of content
            # This ensures AWS SNS can confirm the subscription
            if not raw_data or raw_data.strip() == '':
                app.logger.warning("Empty request body received, returning empty success response")
                return jsonify({'success': True, 'message': 'Empty request acknowledged'})
            
            # Try to parse the JSON content regardless of the Content-Type header
            notification_json = None
            try:
                if request.is_json:
                    notification_json = request.json
                else:
                    # Try to parse the data directly from the request body
                    notification_json = json.loads(raw_data)
            except json.JSONDecodeError as e:
                app.logger.error(f"Failed to parse JSON from request: {str(e)}")
                app.logger.debug(f"Request data: {raw_data}")
                # Instead of failing, return success to prevent SNS from retrying
                return jsonify({'success': True, 'message': f'Invalid JSON acknowledged: {str(e)}'})
            
            if not notification_json:
                app.logger.warning("Could not parse notification_json, returning success to prevent retries")
                return jsonify({'success': True, 'message': 'Empty JSON acknowledged'})
            
            app.logger.info(f"Received SNS notification type: {notification_json.get('Type')}")
            
            # Handle SNS subscription confirmation
            if notification_json.get('Type') == 'SubscriptionConfirmation':
                # Extract the subscription URL and confirm it
                subscribe_url = notification_json.get('SubscribeURL')
                app.logger.info(f"Received subscription URL: {subscribe_url}")
                
                if subscribe_url:
                    # We need to make a GET request to this URL to confirm the subscription
                    import requests
                    try:
                        response = requests.get(subscribe_url)
                        app.logger.info(f"Subscription confirmation response: {response.status_code}")
                        
                        if response.status_code == 200:
                            app.logger.info(f"SNS subscription confirmed. URL: {subscribe_url}")
                            return jsonify({'success': True, 'message': 'Subscription confirmed'})
                        else:
                            app.logger.error(f"Failed to confirm SNS subscription. Status: {response.status_code}")
                            app.logger.error(f"Response: {response.text}")
                    except Exception as e:
                        app.logger.error(f"Error during subscription confirmation: {str(e)}")
                        return jsonify({'success': False, 'message': f'Confirmation error: {str(e)}'})
                
                app.logger.warning("No SubscribeURL found in the request")
                return jsonify({'success': False, 'message': 'Subscription confirmation failed: No URL'})
            
            # Handle actual notification
            if notification_json.get('Type') == 'Notification':
                # Check if SQS is enabled - if so, forward the notification to SQS queue
                if app.config.get('SQS_ENABLED', False):
                    try:
                        # Forward the entire notification to SQS for async processing
                        sqs_handler = app.get_sqs_handler()
                        message_id = sqs_handler.send_message(notification_json)
                        
                        if message_id:
                            app.logger.info(f"Forwarded SNS notification to SQS queue: {message_id}")
                            return jsonify({
                                'success': True, 
                                'message': 'Notification forwarded to SQS for async processing'
                            }), 200
                    except Exception as e:
                        app.logger.error(f"Error forwarding to SQS: {str(e)}", exc_info=True)
                        # Fall back to direct processing if SQS forwarding fails
                        app.logger.warning("Falling back to direct processing due to SQS error")
                        # Continue with normal processing below
                
                # Parse the message payload before doing any logging or processing
                # to quickly identify and handle Send events
                try:
                    message_str = notification_json.get('Message', '{}')
                    message = json.loads(message_str)
                    notification_type = message.get('notificationType') or message.get('eventType')
                    
                    # Ultra-aggressive handling for all non-critical events to prevent server overload
                    # Applied even with SQS enabled for extra protection
                    if notification_type not in ['Bounce', 'Complaint']:
                        # Skip 99.8% of all non-critical notifications to drastically reduce load
                        # This provides an additional safeguard alongside SQS processing
                        if random.random() < 0.998:
                            return jsonify({'success': True, 'message': f'{notification_type} notification acknowledged'}), 200
                except Exception:
                    # If we can't parse, continue with normal processing
                    pass
                    
                # Log the full notification for debugging - only for non-Send events
                # to reduce log volume
                app.logger.info(f"Full notification: {json.dumps(notification_json)[:1000]}...")
                
                # Store the full notification in a log file for debugging
                try:
                    with open('ses_notifications.log', 'a') as f:
                        f.write(f"===== NEW NOTIFICATION {datetime.now().isoformat()} =====\n")
                        f.write(raw_data)
                        f.write("\n\n")
                except Exception as e:
                    app.logger.error(f"Could not write notification to log file: {str(e)}")
                
                # Parse the message payload
                try:
                    message_str = notification_json.get('Message', '{}')
                    app.logger.info(f"Message string: {message_str[:500]}...")
                    
                    message = json.loads(message_str)
                    # Try both notificationType and eventType as AWS SES uses both formats
                    notification_type = message.get('notificationType') or message.get('eventType')
                    
                    app.logger.info(f"Processing SES notification type: {notification_type}")
                    app.logger.info(f"Message details: {json.dumps(message)[:500]}...")
                    
                    # Determine if this is a critical notification that should bypass rate limiting
                    is_critical = notification_type in ['Bounce', 'Complaint']
                    
                    # Apply rate limiting for non-critical notifications
                    if not is_critical and not sns_rate_limiter.consume(tokens=1, bypass=False):
                        app.logger.warning(f"Rate limited {notification_type} notification - too many requests")
                        return jsonify({
                            'success': True, 
                            'message': f'Rate limited {notification_type} notification'
                        }), 200  # Still return 200 so SNS doesn't retry
                    
                    # Handle different notification types
                    if notification_type == 'Bounce':
                        handle_bounce_notification(message)
                    elif notification_type == 'Complaint':
                        handle_complaint_notification(message)
                    elif notification_type == 'Delivery':
                        handle_delivery_notification(message)
                    elif notification_type == 'DeliveryDelay':
                        handle_delivery_delay_notification(message)
                    elif notification_type == 'Send':
                        handle_send_notification(message)
                    elif notification_type == 'Open':
                        handle_open_notification(message)
                    elif notification_type == 'Click':
                        handle_click_notification(message)
                    else:
                        app.logger.warning(f"Unknown notification type: {notification_type}")
                    
                    return jsonify({'success': True, 'message': f'Processed {notification_type} notification'})
                except json.JSONDecodeError as e:
                    app.logger.error(f"Failed to parse Message JSON: {str(e)}")
                    app.logger.debug(f"Message data: {notification_json.get('Message')}")
                    # Instead of failing, return success to prevent SNS from retrying
                    return jsonify({'success': True, 'message': f'Invalid Message JSON: {str(e)}'})
            
            return jsonify({'success': True, 'message': 'Notification received but no action taken'})
        except Exception as e:
            app.logger.error(f"Error processing SNS notification: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'message': f'Error: {str(e)}'})
    
    def handle_bounce_notification(message):
        """Handle bounce notifications from SES"""
        app.logger.info("==== HANDLING BOUNCE NOTIFICATION ====")
        bounce_info = message.get('bounce', {})
        bounce_type = bounce_info.get('bounceType')
        bounce_subtype = bounce_info.get('bounceSubType')
        
        app.logger.info(f"Bounce type: {bounce_type}, subtype: {bounce_subtype}")
        
        # Get the message ID from the mail object
        mail_obj = message.get('mail', {})
        message_id = mail_obj.get('messageId')
        app.logger.info(f"Message ID from notification: {message_id}")
        
        # Log all bounced recipients
        bounce_recipients = bounce_info.get('bouncedRecipients', [])
        app.logger.info(f"Bounced recipients: {bounce_recipients}")
        
        # Process each bounced recipient
        for recipient_info in bounce_recipients:
            email = recipient_info.get('emailAddress')
            if not email:
                app.logger.warning("No email address found in bounce recipient info")
                continue
                
            app.logger.info(f"Processing bounce notification for message ID: {message_id}")
            app.logger.info(f"Updating bounce status for {email} in campaign")
            
            # Find the recipient record
            recipient_record = EmailRecipient.query.filter_by(message_id=message_id, email=email).first()
            
            if not recipient_record:
                app.logger.warning(f"No recipient found with message ID {message_id} and email {email}")
                # Try to find by email only as fallback
                recipient_record = EmailRecipient.query.filter_by(email=email).order_by(EmailRecipient.id.desc()).first()
                if recipient_record:
                    app.logger.info(f"Found recipient by email only (fallback): {recipient_record.id}")
                else:
                    app.logger.error(f"Could not find any recipient with email {email}")
                    continue
            else:
                app.logger.info(f"Found recipient with matching message ID and email: {recipient_record.id}")
                
            # Update the recipient status
            original_status = recipient_record.delivery_status
            recipient_record.delivery_status = 'bounced'
            recipient_record.status = 'failed'
            recipient_record.bounce_type = bounce_type
            recipient_record.bounce_subtype = bounce_subtype
            recipient_record.bounce_time = datetime.now()
            recipient_record.bounce_diagnostic = recipient_info.get('diagnosticCode')
            
            # Update global status for permanent bounces
            # This will mark the recipient as problematic for all future campaigns
            if bounce_type == 'Permanent':
                recipient_record.global_status = 'bounced'
                app.logger.info(f"Set global status to 'bounced' for {email} - this email won't be sent to in future campaigns")
            
            app.logger.info(f"Updated bounce status for {email} from '{original_status}' to 'bounced'")
            
            # Commit the changes
            try:
                db.session.commit()
                app.logger.info(f"Updated bounce status for {email}")
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"Error updating bounce status: {str(e)}")
    
    def handle_complaint_notification(message):
        """Handle complaint notifications from SES"""
        app.logger.info("==== HANDLING COMPLAINT NOTIFICATION ====")
        
        # Extract complaint information
        complaint_info = message.get('complaint', {})
        mail_obj = message.get('mail', {})
        message_id = mail_obj.get('messageId')
        
        # Get the list of recipients that complained
        complaint_recipients = complaint_info.get('complainedRecipients', [])
        
        app.logger.info(f"Message ID from complaint notification: {message_id}")
        app.logger.info(f"Complaint recipients: {complaint_recipients}")
        
        # Process each complaint recipient
        for recipient_info in complaint_recipients:
            email = recipient_info.get('emailAddress')
            if not email:
                app.logger.warning("No email address found in complaint recipient info")
                continue
                
            # Find the recipient record
            recipient_record = EmailRecipient.query.filter_by(message_id=message_id, email=email).first()
            
            if not recipient_record:
                app.logger.warning(f"No recipient found with message ID {message_id} and email {email}")
                # Try to find by email only as fallback
                recipient_record = EmailRecipient.query.filter_by(email=email).order_by(EmailRecipient.id.desc()).first()
                if not recipient_record:
                    app.logger.error(f"Could not find any recipient with email {email}")
                    continue
            
            # Update the recipient status
            recipient_record.status = 'complained'
            
            # Set global status to 'complained' - this will prevent future sends to this email
            recipient_record.global_status = 'complained'
            
            app.logger.info(f"Updated {email} status to 'complained' and set global status to prevent future sends")
            
            # Commit the changes
            try:
                db.session.commit()
                app.logger.info(f"Successfully updated complaint status for {email}")
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"Error updating complaint status: {str(e)}")
        
        # Get complaint type for logging
        complaint_type = complaint_info.get('complaintFeedbackType')
        
        app.logger.info(f"Complaint type: {complaint_type}")
        
        # Get the message ID from the mail object
        mail_obj = message.get('mail', {})
        message_id = mail_obj.get('messageId')
        app.logger.info(f"Message ID from notification: {message_id}")
        
        # Log all complained recipients
        complained_recipients = complaint_info.get('complainedRecipients', [])
        app.logger.info(f"Complained recipients: {complained_recipients}")
        
        # Process each complained recipient
        for recipient_info in complained_recipients:
            email = recipient_info.get('emailAddress')
            if not email:
                app.logger.warning("No email address found in complaint recipient info")
                continue
                
            app.logger.info(f"Processing complaint notification for message ID: {message_id}")
            app.logger.info(f"Updating complaint status for {email} in campaign")
            
            # Find the recipient record
            recipient_record = EmailRecipient.query.filter_by(message_id=message_id, email=email).first()
            
            if not recipient_record:
                app.logger.warning(f"No recipient found with message ID {message_id} and email {email}")
                # Try to find by email only as fallback
                recipient_record = EmailRecipient.query.filter_by(email=email).order_by(EmailRecipient.id.desc()).first()
                if recipient_record:
                    app.logger.info(f"Found recipient by email only (fallback): {recipient_record.id}")
                else:
                    app.logger.error(f"Could not find any recipient with email {email}")
                    continue
            else:
                app.logger.info(f"Found recipient with matching message ID and email: {recipient_record.id}")
                
            # Update the recipient status
            original_status = recipient_record.delivery_status
            recipient_record.delivery_status = 'complained'
            recipient_record.complaint_time = datetime.now()
            
            app.logger.info(f"Updated complaint status for {email} from '{original_status}' to 'complained'")
            
            # Commit the changes
            try:
                db.session.commit()
                app.logger.info(f"Updated complaint status for {email}")
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"Error updating complaint status: {str(e)}")
    
    def handle_delivery_notification(message):
        """Handle delivery notifications from SES"""
        app.logger.info("==== HANDLING DELIVERY NOTIFICATION ====")
        delivery_info = message.get('delivery', {})
        
        # Get the message ID from the mail object
        mail_obj = message.get('mail', {})
        message_id = mail_obj.get('messageId')
        app.logger.info(f"Message ID from notification: {message_id}")
        
        # Log all recipients
        recipients = delivery_info.get('recipients', [])
        app.logger.info(f"Delivered recipients: {recipients}")
        
        for email in recipients:
            app.logger.info(f"Processing delivery notification for {email} with message ID: {message_id}")
            
            # Find the recipient record
            recipient_record = EmailRecipient.query.filter_by(message_id=message_id, email=email).first()
            
            if not recipient_record:
                app.logger.warning(f"No recipient found with message ID {message_id} and email {email}")
                # Try to find by email only as fallback
                recipient_record = EmailRecipient.query.filter_by(email=email).order_by(EmailRecipient.id.desc()).first()
                if recipient_record:
                    app.logger.info(f"Found recipient by email only (fallback): {recipient_record.id}")
                else:
                    app.logger.error(f"Could not find any recipient with email {email}")
                    continue
            else:
                app.logger.info(f"Found recipient with matching message ID and email: {recipient_record.id}")
                
            # Update the recipient status
            original_status = recipient_record.delivery_status
            recipient_record.delivery_status = 'delivered'
            recipient_record.delivery_time = datetime.now()
            
            app.logger.info(f"Updated delivery status for {email} from '{original_status}' to 'delivered'")
            
            # Commit the changes
            try:
                db.session.commit()
                app.logger.info(f"Updated delivery status for {email}")
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"Error updating delivery status: {str(e)}")
    
    def handle_delivery_delay_notification(message):
        """Handle delivery delay notifications from SES"""
        app.logger.info("==== HANDLING DELIVERY DELAY NOTIFICATION ====")
        delay_info = message.get('deliveryDelay', {})
        
        # Get the message ID from the mail object
        mail_obj = message.get('mail', {})
        message_id = mail_obj.get('messageId')
        app.logger.info(f"Message ID from notification: {message_id}")
        
        # Get delay-specific information
        delay_type = delay_info.get('delayType', 'Unknown')
        timestamp = delay_info.get('timestamp')
        
        # Log all delayed recipients
        delayed_recipients = delay_info.get('delayedRecipients', [])
        app.logger.info(f"Delayed recipients: {delayed_recipients}")
        app.logger.info(f"Delivery delay type: {delay_type}")
        app.logger.info(f"Delivery delay timestamp: {timestamp}")
        
        # Process each recipient
        for recipient_info in delayed_recipients:
            email = recipient_info.get('emailAddress')
            if not email:
                app.logger.warning("No email address found in delayed recipient info")
                continue
            
            app.logger.info(f"Processing delivery delay notification for {email} with message ID: {message_id}")
            
            # Find the recipient record
            recipient_record = EmailRecipient.query.filter_by(message_id=message_id, email=email).first()
            
            if not recipient_record:
                app.logger.warning(f"No recipient found with message ID {message_id} and email {email}")
                # Try to find by email only as fallback
                recipient_record = EmailRecipient.query.filter_by(email=email).order_by(EmailRecipient.id.desc()).first()
                if recipient_record:
                    app.logger.info(f"Found recipient by email only (fallback): {recipient_record.id}")
                else:
                    app.logger.error(f"Could not find any recipient with email {email}")
                    continue
            else:
                app.logger.info(f"Found recipient with matching message ID and email: {recipient_record.id}")
                
            # Update the recipient status
            original_status = recipient_record.delivery_status
            recipient_record.delivery_status = 'delayed'
            recipient_record.delay_type = delay_type
            recipient_record.delay_time = datetime.now()
            
            app.logger.info(f"Updated delivery status for {email} from '{original_status}' to 'delayed'")
            
            # Commit the changes
            try:
                db.session.commit()
                app.logger.info(f"Updated delay status for {email}")
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"Error updating delay status: {str(e)}")
    
    def handle_send_notification(message):
        """Handle send notifications from SES"""
        app.logger.info("==== HANDLING SEND NOTIFICATION ====")
        
        # Get the message ID from the mail object
        mail_obj = message.get('mail', {})
        message_id = mail_obj.get('messageId')
        app.logger.info(f"Message ID from send notification: {message_id}")
        
        # Get recipients
        recipients = mail_obj.get('destination', [])
        app.logger.info(f"Send notification recipients: {recipients}")
        
        for email in recipients:
            app.logger.info(f"Processing send notification for {email} with message ID: {message_id}")
            
            # Find the recipient record
            recipient_record = EmailRecipient.query.filter_by(message_id=message_id, email=email).first()
            
            if not recipient_record:
                app.logger.warning(f"No recipient found with message ID {message_id} and email {email}")
                # Try to find by email only as fallback
                recipient_record = EmailRecipient.query.filter_by(email=email).order_by(EmailRecipient.id.desc()).first()
                if recipient_record:
                    app.logger.info(f"Found recipient by email only (fallback): {recipient_record.id}")
                else:
                    app.logger.error(f"Could not find any recipient with email {email}")
                    continue
            else:
                app.logger.info(f"Found recipient with matching message ID and email: {recipient_record.id}")
                
            # Update the recipient status if it doesn't already have a status
            if recipient_record.delivery_status in [None, '', 'queued', 'scheduled']:
                original_status = recipient_record.delivery_status
                recipient_record.delivery_status = 'sent'
                recipient_record.sent_time = datetime.now()
                
                app.logger.info(f"Updated status for {email} from '{original_status}' to 'sent'")
                
                # Commit the changes
                try:
                    db.session.commit()
                    app.logger.info(f"Updated send status for {email}")
                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"Error updating send status: {str(e)}")
        
        for recipient_info in delayed_recipients:
            email = recipient_info.get('emailAddress')
            if not email:
                app.logger.warning("No email address found in delay recipient info")
                continue
                
            app.logger.info(f"Processing delay notification for message ID: {message_id}")
            app.logger.info(f"Updating delay status for {email} in campaign")
            
            # Find the recipient record
            recipient_record = EmailRecipient.query.filter_by(message_id=message_id, email=email).first()
            
            if not recipient_record:
                app.logger.warning(f"No recipient found with message ID {message_id} and email {email}")
                # Try to find by email only as fallback
                recipient_record = EmailRecipient.query.filter_by(email=email).order_by(EmailRecipient.id.desc()).first()
                if recipient_record:
                    app.logger.info(f"Found recipient by email only (fallback): {recipient_record.id}")
                else:
                    app.logger.error(f"Could not find any recipient with email {email}")
                    continue
            else:
                app.logger.info(f"Found recipient with matching message ID and email: {recipient_record.id}")
                
            # Update the recipient status
            original_status = recipient_record.delivery_status
            recipient_record.delivery_status = 'delayed'
            recipient_record.delay_time = datetime.now()
            
            app.logger.info(f"Updated delay status for {email} from '{original_status}' to 'delayed'")
            
            # Commit the changes
            try:
                db.session.commit()
                app.logger.info(f"Updated delay status for {email}")
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"Error updating delay status: {str(e)}")
    
    def handle_open_notification(message):
        """Handle open notifications from SES"""
        app.logger.info("==== HANDLING OPEN NOTIFICATION ====")
        open_info = message.get('open', {})
        
        # Get the message ID from the mail object
        mail_obj = message.get('mail', {})
        message_id = mail_obj.get('messageId')
        app.logger.info(f"Message ID from notification: {message_id}")
        
        # Log all opened recipients
        opened_recipients = open_info.get('recipients', [])
        app.logger.info(f"Opened recipients: {opened_recipients}")
        
        for email in opened_recipients:
            app.logger.info(f"Processing open notification for {email} with message ID: {message_id}")
            
            # Find the recipient record
            recipient_record = EmailRecipient.query.filter_by(message_id=message_id, email=email).first()
            
            if not recipient_record:
                app.logger.warning(f"No recipient found with message ID {message_id} and email {email}")
                # Try to find by email only as fallback
                recipient_record = EmailRecipient.query.filter_by(email=email).order_by(EmailRecipient.id.desc()).first()
                if recipient_record:
                    app.logger.info(f"Found recipient by email only (fallback): {recipient_record.id}")
                else:
                    app.logger.error(f"Could not find any recipient with email {email}")
                    continue
            else:
                app.logger.info(f"Found recipient with matching message ID and email: {recipient_record.id}")
                
            # Update the recipient status
            original_status = recipient_record.delivery_status
            recipient_record.delivery_status = 'opened'
            recipient_record.open_time = datetime.now()
            recipient_record.open_count = recipient_record.open_count + 1 if recipient_record.open_count else 1
            
            app.logger.info(f"Updated open status for {email} from '{original_status}' to 'opened'")
            
            # Commit the changes
            try:
                db.session.commit()
                app.logger.info(f"Updated open status for {email}")
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"Error updating open status: {str(e)}")
    
    def handle_click_notification(message):
        """Handle click notifications from SES"""
        app.logger.info("==== HANDLING CLICK NOTIFICATION ====")
        click_info = message.get('click', {})
        
        # Get the message ID from the mail object
        mail_obj = message.get('mail', {})
        message_id = mail_obj.get('messageId')
        app.logger.info(f"Message ID from notification: {message_id}")
        
        # Log all clicked recipients
        clicked_recipients = click_info.get('recipients', [])
        app.logger.info(f"Clicked recipients: {clicked_recipients}")
        
        for email in clicked_recipients:
            app.logger.info(f"Processing click notification for {email} with message ID: {message_id}")
            
            # Find the recipient record
            recipient_record = EmailRecipient.query.filter_by(message_id=message_id, email=email).first()
            
            if not recipient_record:
                app.logger.warning(f"No recipient found with message ID {message_id} and email {email}")
                # Try to find by email only as fallback
                recipient_record = EmailRecipient.query.filter_by(email=email).order_by(EmailRecipient.id.desc()).first()
                if recipient_record:
                    app.logger.info(f"Found recipient by email only (fallback): {recipient_record.id}")
                else:
                    app.logger.error(f"Could not find any recipient with email {email}")
                    continue
            else:
                app.logger.info(f"Found recipient with matching message ID and email: {recipient_record.id}")
                
            # Update the recipient status
            original_status = recipient_record.delivery_status
            recipient_record.delivery_status = 'clicked'
            recipient_record.click_time = datetime.now()
            recipient_record.click_count = recipient_record.click_count + 1 if recipient_record.click_count else 1
            
            app.logger.info(f"Updated click status for {email} from '{original_status}' to 'clicked'")
            
            # Commit the changes
            try:
                db.session.commit()
                app.logger.info(f"Updated click status for {email}")
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"Error updating click status: {str(e)}")
    
    @app.route('/reports/bounces')
    def bounce_report():
        """Show a report of all bounced emails"""
        # Get bounced emails
        bounced_emails = EmailRecipient.query.filter_by(delivery_status='bounced').all()
        
        # Get complaint emails
        complaint_emails = EmailRecipient.query.filter_by(delivery_status='complained').all()
        
        # Get delivery statistics
        stats = {
            'delivered': EmailRecipient.query.filter_by(delivery_status='delivered').count(),
            'bounced': len(bounced_emails),
            'complained': len(complaint_emails),
            'sent': EmailRecipient.query.filter_by(delivery_status='sent').count(),
            'total': EmailRecipient.query.count()
        }
        
        return render_template(
            'bounce_report.html',
            bounced_emails=bounced_emails,
            complaint_emails=complaint_emails,
            stats=stats
        )
    
    @app.route('/recipients/verify', methods=['GET', 'POST'])
    def verify_recipients():
        """Verify email addresses in a campaign"""
        if request.method == 'POST':
            campaign_id = request.form.get('campaign_id')
            
            if not campaign_id:
                flash('Campaign ID is required.', 'danger')
                return redirect(url_for('campaigns'))
            
            campaign = EmailCampaign.query.get_or_404(campaign_id)
            
            # Get all recipients for the campaign
            recipients = EmailRecipient.query.filter_by(campaign_id=campaign_id).all()
            
            if not recipients:
                flash('No recipients found for this campaign.', 'warning')
                return redirect(url_for('campaign_detail', campaign_id=campaign_id))
            
            # Get list of email addresses
            emails = [r.email for r in recipients]
            
            # Start verification in background
            @copy_current_request_context
            def verify_emails_task():
                results = app.email_verifier.batch_verify(emails)
                
                # Update recipient records with verification results
                with app.app_context():
                    for status, email_list in results.items():
                        for email in email_list:
                            recipient = EmailRecipient.query.filter_by(
                                campaign_id=campaign_id, 
                                email=email
                            ).first()
                            
                            if recipient:
                                recipient.is_verified = (status == 'valid')
                                recipient.verification_result = status
                                recipient.verification_date = datetime.utcnow()
                    
                    db.session.commit()
                    
                    # Update campaign verification status
                    campaign.verification_status = 'Complete'
                    db.session.commit()
            
            # Start verification in a separate thread
            import threading
            verify_thread = threading.Thread(target=verify_emails_task)
            verify_thread.daemon = True
            verify_thread.start()
            
            # Update campaign status
            campaign.verification_status = 'In Progress'
            db.session.commit()
            
            flash(f'Email verification started for {len(emails)} recipients. This may take a few minutes.', 'info')
            return redirect(url_for('campaign_detail', campaign_id=campaign_id))
        
        # GET request - show form
        campaigns = EmailCampaign.query.all()
        return render_template('verify_recipients.html', campaigns=campaigns)
    
    @app.route('/reports/tracking', methods=['GET'])
    def tracking_report():
        """Show email tracking report (opens and clicks)"""
        campaign_id = request.args.get('campaign_id')
        
        if campaign_id:
            campaign = EmailCampaign.query.get_or_404(campaign_id)
            
            # Get tracking statistics for this campaign
            
            # Get open data
            open_stats = db.session.query(
                EmailRecipient.id,
                EmailRecipient.email,
                EmailRecipient.open_count,
                EmailRecipient.last_opened_at
            ).filter(
                EmailRecipient.campaign_id == campaign_id,
                EmailRecipient.open_count > 0
            ).order_by(EmailRecipient.open_count.desc()).all()
            
            # Get click data
            click_stats = db.session.query(
                EmailRecipient.id,
                EmailRecipient.email,
                EmailRecipient.click_count,
                EmailRecipient.last_clicked_at
            ).filter(
                EmailRecipient.campaign_id == campaign_id,
                EmailRecipient.click_count > 0
            ).order_by(EmailRecipient.click_count.desc()).all()
            
            # Get summary stats
            total_recipients = EmailRecipient.query.filter_by(campaign_id=campaign_id).count()
            total_opens = EmailRecipient.query.filter(
                EmailRecipient.campaign_id == campaign_id,
                EmailRecipient.open_count > 0
            ).count()
            total_clicks = EmailRecipient.query.filter(
                EmailRecipient.campaign_id == campaign_id,
                EmailRecipient.click_count > 0
            ).count()
            
            # Calculate percentages
            open_rate = round((total_opens / total_recipients * 100) if total_recipients else 0, 2)
            click_rate = round((total_clicks / total_recipients * 100) if total_recipients else 0, 2)
            click_to_open_rate = round((total_clicks / total_opens * 100) if total_opens else 0, 2)
            
            summary = {
                'total_recipients': total_recipients,
                'total_opens': total_opens,
                'total_clicks': total_clicks,
                'open_rate': open_rate,
                'click_rate': click_rate,
                'click_to_open_rate': click_to_open_rate
            }
            
            return render_template(
                'tracking_report.html',
                campaign=campaign,
                open_stats=open_stats,
                click_stats=click_stats,
                summary=summary
            )
        
        # No campaign selected, show list of campaigns
        campaigns = EmailCampaign.query.all()
        return render_template('tracking_campaigns.html', campaigns=campaigns)
    
    @app.route('/tracking', methods=['GET'])
    def tracking_campaigns():
        """Show list of campaigns for tracking data"""
        # Get all campaigns with any status (previously only showed certain statuses)
        campaigns = EmailCampaign.query.order_by(EmailCampaign.created_at.desc()).all()
        
        # Get counts for each campaign
        campaign_data = []
        for campaign in campaigns:
            recipients = EmailRecipient.query.filter_by(campaign_id=campaign.id).all()
            opens = sum(1 for r in recipients if r.open_count and r.open_count > 0)
            clicks = sum(1 for r in recipients if r.click_count and r.click_count > 0)
            
            campaign_data.append({
                'campaign': campaign,
                'recipients': len(recipients),
                'opens': opens,
                'clicks': clicks
            })
        
        return render_template(
            'tracking_campaigns.html',
            campaigns=campaign_data
        )
    
    @app.route('/tracking/report/<int:campaign_id>', methods=['GET'])
    def tracking_report_campaign(campaign_id):
        """Show detailed tracking report for a specific campaign"""
        campaign = EmailCampaign.query.get_or_404(campaign_id)
        
        # Get all recipients for this campaign
        recipients = EmailRecipient.query.filter_by(campaign_id=campaign_id).all()
        
        # Calculate summary statistics
        total_recipients = len(recipients)
        total_opens = sum(1 for r in recipients if r.open_count and r.open_count > 0)
        total_clicks = sum(1 for r in recipients if r.click_count and r.click_count > 0)
        
        # Calculate rates (with zero division protection)
        open_rate = round((total_opens / total_recipients) * 100, 1) if total_recipients > 0 else 0
        click_rate = round((total_clicks / total_recipients) * 100, 1) if total_recipients > 0 else 0
        click_to_open_rate = round((total_clicks / total_opens) * 100, 1) if total_opens > 0 else 0
        
        # Create summary object
        summary = {
            'total_recipients': total_recipients,
            'total_opens': total_opens,
            'total_clicks': total_clicks,
            'open_rate': open_rate,
            'click_rate': click_rate,
            'click_to_open_rate': click_to_open_rate
        }
        
        # Get recipients who opened emails
        open_stats = [r for r in recipients if r.open_count and r.open_count > 0]
        open_stats.sort(key=lambda x: x.open_count or 0, reverse=True)
        
        # Get recipients who clicked links
        click_stats = [r for r in recipients if r.click_count and r.click_count > 0]
        click_stats.sort(key=lambda x: x.click_count or 0, reverse=True)
        
        return render_template(
            'tracking_report.html',
            campaign=campaign,
            summary=summary,
            open_stats=open_stats,
            click_stats=click_stats
        )
    
    # API Endpoints
    @app.route('/api/campaigns/<int:campaign_id>/status', methods=['PUT'])
    def update_campaign_status(campaign_id):
        campaign = EmailCampaign.query.get_or_404(campaign_id)
        data = request.json
        
        if 'status' not in data:
            return jsonify({'error': 'Status field is required'}), 400
            
        # Validate status
        valid_statuses = ['draft', 'scheduled', 'in_progress', 'completed', 'failed']
        if data['status'] not in valid_statuses:
            return jsonify({'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400
            
        campaign.status = data['status']
        campaign.updated_at = datetime.now()
        db.session.commit()
        
        return jsonify({
            'id': campaign.id,
            'status': campaign.status,
            'message': 'Status updated successfully'
        })
    
    @app.route('/api/campaigns/<int:campaign_id>/send', methods=['POST'])
    def trigger_campaign_send(campaign_id):
        campaign = EmailCampaign.query.get_or_404(campaign_id)
        
        # Check if campaign can be sent
        if campaign.status in ['in_progress', 'completed']:
            return jsonify({
                'success': False,
                'message': f'Campaign is already {campaign.status}'
            })
        
        # Verify recipients exist
        recipient_count = EmailRecipient.query.filter_by(campaign_id=campaign_id).count()
        if recipient_count == 0:
            return jsonify({
                'success': False,
                'message': 'Campaign has no recipients'
            })
        
        try:
            # Send campaign immediately
            app.get_scheduler().send_campaign(campaign)
            
            return jsonify({
                'success': True,
                'message': 'Campaign sending started'
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error sending campaign: {str(e)}'
            })
    
    @app.route('/api/campaigns/<int:campaign_id>/send-test', methods=['POST'])
    def api_send_test_recipient(campaign_id):
        """Send a test email for the campaign"""
        try:
            campaign = EmailCampaign.query.get_or_404(campaign_id)
            
            # Get the destination email from the request
            data = request.json if request.is_json else request.form
            email = data.get('email')
            
            if not email:
                return jsonify({'success': False, 'message': 'Email address is required'})
            
            # Create a test recipient in the database so we can track bounces
            test_recipient = EmailRecipient.query.filter_by(
                campaign_id=campaign_id, 
                email=email, 
                is_test=True
            ).first()
            
            # If this test email doesn't exist yet, create it
            if not test_recipient:
                test_recipient = EmailRecipient(
                    campaign_id=campaign_id,
                    email=email,
                    name="Test Recipient",
                    status="pending",
                    is_test=True
                )
                db.session.add(test_recipient)
                db.session.commit()
            # If it exists but previously failed, reset it for a new attempt
            elif test_recipient.status == 'failed':
                test_recipient.status = 'pending'
                test_recipient.error_message = None
                test_recipient.delivery_status = None
                test_recipient.bounce_type = None
                test_recipient.bounce_subtype = None
                test_recipient.bounce_time = None
                test_recipient.bounce_diagnostic = None
                db.session.commit()
            
            # Create HTML and text content
            html_content = campaign.body_html
            text_content = campaign.body_text
            
            # Send the email
            email_service = app.get_email_service()
            
            # Debug logging
            app.logger.info(f"Sending test email with sender: {campaign.sender_email}")
            
            message_id = email_service.send_email(
                recipient=email,
                subject=f"[TEST] {campaign.subject}",
                body_html=html_content,
                body_text=text_content,
                campaign_id=campaign_id,
                recipient_id=test_recipient.id
            )
            
            # Update the recipient status
            if message_id:
                test_recipient.status = 'sent'
                test_recipient.sent_at = datetime.now()
                test_recipient.message_id = message_id
                test_recipient.delivery_status = 'sent'
                
                app.logger.info(f"Test email sent to {email} with message ID: {test_recipient.message_id}")
                
                # Commit the changes
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'message': 'Test email sent successfully! Check your inbox.'
                })
            else:
                # Update failure status
                test_recipient.status = 'failed'
                test_recipient.error_message = 'Unknown error'
                db.session.commit()
                
                app.logger.error(f"Failed to send test email to {email}: {test_recipient.error_message}")
                
                return jsonify({
                    'success': False,
                    'message': f"Failed to send email: {test_recipient.error_message}"
                })
        except Exception as e:
            app.logger.error(f"Error sending test email: {str(e)}", exc_info=True)  # Added exc_info for stack trace
            return jsonify({
                'success': False,
                'message': f'Error: {str(e)}'
            })
    
    @app.route('/api/campaigns/<int:campaign_id>/test-email', methods=['POST'])
    def api_send_test_email(campaign_id):
        campaign = EmailCampaign.query.get_or_404(campaign_id)
        data = request.get_json()
        
        if not data or 'email' not in data:
            return jsonify({'success': False, 'message': 'Email address is required'}), 400
        
        # Send test email
        email_service = app.get_email_service()
        try:
            # Debug logging to help diagnose issues
            app.logger.info(f"Sending test email using sender: {campaign.sender_email}")
            
            # Create a recipient record first so we have an ID for tracking
            test_recipient = EmailRecipient(
                campaign_id=campaign.id,
                email=data['email'],
                status='sending',
                delivery_status='pending',
                sent_at=datetime.now()
            )
            db.session.add(test_recipient)
            db.session.commit()
            
            # Now send the email with tracking parameters
            message_id = email_service.send_email(
                recipient=data['email'],
                subject=f"[TEST] {campaign.subject}",
                body_html=campaign.body_html,
                body_text=campaign.body_text,
                campaign_id=campaign.id,
                recipient_id=test_recipient.id  # Pass recipient ID for tracking
            )
            
            # Update the recipient record if email was sent
            if message_id:
                test_recipient.status = 'sent'
                test_recipient.message_id = message_id
                test_recipient.delivery_status = 'sent'
                db.session.commit()
                
                app.logger.info(f"Test email sent to {data['email']} with message_id={message_id}")
                app.logger.info(f"Added test recipient to campaign {campaign.id} for status tracking")
                return jsonify({
                    'success': True,
                    'message': 'Test email sent successfully!'
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'Failed to send test email'
                })
        except Exception as e:
            app.logger.error(f"Error sending test email: {str(e)}", exc_info=True)
            return jsonify({
                'success': False,
                'message': f'Error sending test email: {str(e)}'
            })
    
    @app.route('/api/process-sqs-queue', methods=['GET'])
    def process_sqs_queue():
        """
        Process messages from the SQS queue that contains SNS notifications.
        
        This endpoint is intended to be called periodically via a cron job or JavaScript
        to control the rate at which notifications are processed, avoiding server overload
        on Render's free tier during large campaigns (up to 40k emails).
        
        Benefits:
        1. Preserves all notifications (unlike the token bucket which drops 99.5% of non-critical ones)
        2. Processes notifications at a controlled rate to prevent 502 errors
        3. Operates within Render's free tier performance constraints
        4. Maintains handling of all notification types for better analytics
        
        Returns 200 OK with count of processed messages or error details.
        """
        if not app.config.get('SQS_ENABLED', False):
            return jsonify({"status": "disabled", "message": "SQS processing is disabled"}), 200
            
        try:
            sqs_handler = app.get_sqs_handler()
            max_messages = request.args.get('max', 10, type=int)
            if max_messages > 10:
                max_messages = 10  # SQS API limit is 10
                
            # Get messages from queue
            messages = sqs_handler.receive_messages(
                max_messages=max_messages,
                wait_time=1,
                visibility_timeout=60  # 1 minute to process
            )
            
            if not messages:
                return jsonify({"status": "success", "processed": 0, "message": "No messages in queue"})
                
            # Process each message
            processed_count = 0
            for message in messages:
                try:
                    # Parse and handle SNS notification
                    receipt_handle = message['ReceiptHandle']
                    
                    # Safely parse message body
                    raw_body = message.get('Body', '')
                    if not raw_body or not raw_body.strip():
                        app.logger.warning("Empty message body, skipping")
                        sqs_handler.delete_message(receipt_handle)
                        continue
                        
                    try:
                        body = json.loads(raw_body)
                    except json.JSONDecodeError as json_err:
                        app.logger.warning(f"Invalid JSON in message body: {str(json_err)}")
                        # Delete invalid messages to prevent queue build-up
                        sqs_handler.delete_message(receipt_handle)
                        continue
                    
                    # If this is an SNS message, extract the actual message
                    if 'Message' in body:
                        # For processing, use the existing notification handler logic
                        raw_message = body.get('Message', '')
                        if not raw_message or not isinstance(raw_message, str):
                            app.logger.warning("Invalid SNS message format, skipping")
                            sqs_handler.delete_message(receipt_handle)
                            continue
                            
                        try:
                            sns_message = json.loads(raw_message)
                        except json.JSONDecodeError as json_err:
                            app.logger.warning(f"Invalid JSON in SNS message: {str(json_err)}")
                            sqs_handler.delete_message(receipt_handle)
                            continue
                            
                        notification_type = sns_message.get('notificationType') or sns_message.get('eventType')
                        
                        app.logger.info(f"Processing SQS message with notification type: {notification_type}")
                        
                        # Process the notification using existing handlers
                        if notification_type == 'Bounce':
                            handle_bounce_notification(sns_message)
                        elif notification_type == 'Complaint':
                            handle_complaint_notification(sns_message)
                        elif notification_type == 'Delivery':
                            handle_delivery_notification(sns_message)
                        elif notification_type == 'DeliveryDelay':
                            handle_delivery_delay_notification(sns_message)
                        elif notification_type == 'Open':
                            handle_open_notification(sns_message)
                        elif notification_type == 'Click':
                            handle_click_notification(sns_message)
                    
                    # Delete the message from the queue after processing
                    sqs_handler.delete_message(receipt_handle)
                    processed_count += 1
                    
                except Exception as e:
                    app.logger.error(f"Error processing SQS message: {str(e)}", exc_info=True)
                    # Delete the message to prevent queue build-up with problematic messages
                    try:
                        if 'receipt_handle' in locals():
                            sqs_handler.delete_message(receipt_handle)
                            app.logger.info("Message deleted from SQS queue")
                    except Exception as delete_err:
                        app.logger.error(f"Error deleting message: {str(delete_err)}")
                    # Continue with other messages
            
            return jsonify({"status": "success", "processed": processed_count})
            
        except Exception as e:
            app.logger.error(f"Error processing SQS queue: {str(e)}", exc_info=True)
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route('/api/diagnostics/ses-config-set', methods=['GET'])
    def check_ses_config_set():
        """Check if the SES configuration set is accessible"""
        try:
            email_service = app.get_email_service()
            email_service._ensure_client()
            
            # Try to list configuration sets
            config_sets = email_service.client.list_configuration_sets()
            
            # Check if our configuration set exists
            config_set_names = [cs.get('Name') for cs in config_sets.get('ConfigurationSets', [])]
            target_config_set = 'email-bulk-scheduler-config'
            
            return jsonify({
                'success': True,
                'aws_region': email_service.region_name,
                'configuration_sets_found': config_set_names,
                'target_config_set': target_config_set,
                'target_exists': target_config_set in config_set_names
            })
        except Exception as e:
            app.logger.error(f"Error checking SES configuration set: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            })

    @app.route('/api/campaigns/<int:campaign_id>/progress', methods=['GET'])
    def get_campaign_progress(campaign_id):
        """API endpoint to get real-time campaign progress"""
        try:
            campaign = EmailCampaign.query.get_or_404(campaign_id)
            
            # Get counts of different statuses
            total_recipients = EmailRecipient.query.filter_by(campaign_id=campaign_id).count()
            sent_count = EmailRecipient.query.filter_by(campaign_id=campaign_id, status='sent').count()
            failed_count = EmailRecipient.query.filter_by(campaign_id=campaign_id, status='failed').count()
            pending_count = total_recipients - sent_count - failed_count
            
            # Calculate progress percentage
            progress_percentage = 0
            if total_recipients > 0:
                progress_percentage = int(((sent_count + failed_count) / total_recipients) * 100)
            
            # Calculate estimated time remaining based on current rate
            # For running campaigns only
            estimated_time_remaining = None
            if campaign.status == 'running' and campaign.started_at and sent_count > 0:
                elapsed_time = (datetime.now() - campaign.started_at).total_seconds()
                if elapsed_time > 0:
                    emails_per_second = sent_count / elapsed_time
                    if emails_per_second > 0:
                        remaining_emails = total_recipients - sent_count - failed_count
                        est_seconds_remaining = remaining_emails / emails_per_second
                        estimated_time_remaining = int(est_seconds_remaining)
            
            return jsonify({
                'success': True,
                'campaign': {
                    'id': campaign.id,
                    'name': campaign.name,
                    'status': campaign.status,
                    'total_recipients': total_recipients,
                    'sent_count': sent_count,
                    'failed_count': failed_count,
                    'pending_count': pending_count,
                    'progress_percentage': progress_percentage,
                    'estimated_time_remaining': estimated_time_remaining
                }
            })
        except Exception as e:
            app.logger.error(f"Error getting campaign progress: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/campaigns/<int:campaign_id>/recipients', methods=['GET'])
    def get_campaign_recipients(campaign_id):
        """API endpoint to fetch recipients for a campaign"""
        try:
            recipients = EmailRecipient.query.filter_by(campaign_id=campaign_id).all()
            recipients_data = []
            
            for recipient in recipients:
                recipients_data.append({
                    'id': recipient.id,
                    'email': recipient.email,
                    'name': recipient.name or '-',
                    'status': recipient.status,
                    'delivery_status': recipient.delivery_status,
                    'sent_at': recipient.sent_at.isoformat() if recipient.sent_at else None,
                    'bounce_type': recipient.bounce_type,
                    'bounce_subtype': recipient.bounce_subtype,
                    'error_message': recipient.error_message
                })
            
            return jsonify({
                'success': True,
                'recipients': recipients_data
            })
        except Exception as e:
            app.logger.error(f"Error fetching recipients: {str(e)}")
            return jsonify({
                'success': False,
                'message': f"Error fetching recipients: {str(e)}"
            }), 500
    
    @app.route('/campaigns/<int:campaign_id>/test_send_button')
    def test_send_button(campaign_id):
        """Test page for debugging send button functionality"""
        campaign = EmailCampaign.query.get_or_404(campaign_id)
        return render_template('send_button_test.html', campaign_id=campaign_id)
    
    @app.route('/api-test')
    def api_test():
        """Diagnostic page to test API endpoints directly"""
        return render_template('api_test.html')

    @app.route('/direct-test')
    def direct_test():
        """Direct testing page with minimal dependencies"""
        return render_template('direct_test.html')

    @app.route('/campaigns/<int:campaign_id>/start-form', methods=['POST'])
    def start_campaign_form(campaign_id):
        """Start campaign using a traditional form submission"""
        app.logger.info(f"START CAMPAIGN FORM ENDPOINT CALLED for campaign_id={campaign_id}")
        try:
            campaign = EmailCampaign.query.get_or_404(campaign_id)
            
            # Update campaign status to in_progress
            campaign.status = 'in_progress'
            db.session.commit()
            
            # Get the scheduler and send the campaign
            scheduler = app.get_scheduler()
            result = scheduler.send_campaign(campaign)
            app.logger.info(f"Campaign {campaign_id} form send result: {result}")
            
            flash('Campaign sending has started!', 'success')
            return redirect(url_for('campaign_detail', campaign_id=campaign_id))
        except Exception as e:
            app.logger.error(f"Error starting campaign via form: {str(e)}")
            flash(f'Error starting campaign: {str(e)}', 'danger')
            return redirect(url_for('campaign_detail', campaign_id=campaign_id))

    @app.route('/campaigns/<int:campaign_id>/test-email-form', methods=['POST'])
    def send_test_email_form(campaign_id):
        """Send test email using a traditional form submission"""
        app.logger.info(f"SEND TEST EMAIL FORM ENDPOINT CALLED for campaign_id={campaign_id}")
        try:
            campaign = EmailCampaign.query.get_or_404(campaign_id)
            test_email = request.form.get('email')
            
            if not test_email:
                flash('Please provide an email address', 'warning')
                return redirect(url_for('campaign_detail', campaign_id=campaign_id))
            
            # Get email service and send test email
            email_service = app.get_email_service()
            
            # Ensure the email service is properly initialized with sender email
            email_service._ensure_client()
            
            # Log the current environment variables for debugging
            app.logger.info(f"Using sender email: {email_service.sender_email}")
            app.logger.info(f"Using configuration set: {email_service.configuration_set}")
            
            # Create a recipient record first so we have an ID for tracking
            test_recipient = EmailRecipient(
                campaign_id=campaign.id,
                email=test_email,
                status='sending',
                delivery_status='pending',
                sent_at=datetime.now()
            )
            db.session.add(test_recipient)
            db.session.commit()
            
            # Now send the email with tracking parameters
            message_id = email_service.send_email(
                recipient=test_email,
                subject=f"TEST: {campaign.subject}",
                body_html=campaign.body_html,
                body_text=campaign.body_text,
                campaign_id=campaign.id,
                recipient_id=test_recipient.id  # Pass recipient ID for tracking
            )
            
            # Update the recipient record if email was sent
            if message_id:
                test_recipient.status = 'sent'
                test_recipient.message_id = message_id
                test_recipient.delivery_status = 'sent'
                db.session.commit()
                
                app.logger.info(f"Test email sent to {test_email} with message_id={message_id}")
                app.logger.info(f"Added test recipient to campaign {campaign.id} for status tracking")
                flash(f'Test email sent to {test_email} with tracking enabled', 'success')
            else:
                app.logger.error(f"Failed to send test email to {test_email} - no message ID returned")
                flash(f'Failed to send test email. Check logs for details.', 'danger')
            
            return redirect(url_for('campaign_detail', campaign_id=campaign_id))
        except Exception as e:
            app.logger.error(f"Error sending test email via form: {str(e)}")
            flash(f'Error sending test email: {str(e)}', 'danger')
            return redirect(url_for('campaign_detail', campaign_id=campaign_id))
    
    # Add a batch processing endpoint for scheduled processing
    @app.route('/api/process-emails', methods=['POST'])
    def process_emails_api():
        """
        API endpoint to process a batch of pending emails.
        
        This endpoint can be called by a scheduler or cron job to process
        emails even on Render's free tier without a dedicated worker.
        
        Returns:
            JSON response with status and count of processed emails
        """
        # Check for optional authorization token
        auth_token = request.headers.get('Authorization')
        expected_token = os.environ.get('API_PROCESS_TOKEN')
        
        if expected_token and auth_token != f"Bearer {expected_token}":
            return jsonify({"status": "error", "message": "Unauthorized"}), 401
        
        try:
            # Process a batch of emails
            count = process_pending_emails(limit=10)
            return jsonify({
                "status": "success",
                "processed": count,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            app.logger.error(f"Error processing emails: {str(e)}")
            return jsonify({
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }), 500

    def process_pending_emails(limit=10):
        """
        Process a batch of pending emails from campaigns.
        
        Args:
            limit: Maximum number of emails to process in this batch
        
        Returns:
            Count of processed emails
        """
        count = 0
        
        # Get campaigns that are in progress
        campaigns = EmailCampaign.query.filter_by(status='in_progress').all()
        
        for campaign in campaigns:
            # Get pending recipients for this campaign
            recipients = EmailRecipient.query.filter_by(
                campaign_id=campaign.id,
                status='pending'
            ).limit(limit - count).all()
            
            if not recipients:
                continue
            
            # Get email service
            email_service = app.get_email_service()
            
            # Process each recipient
            for recipient in recipients:
                try:
                    # Get recipient's custom data
                    custom_data = {}
                    if hasattr(recipient, 'custom_data') and recipient.custom_data:
                        try:
                            custom_data = json.loads(recipient.custom_data)
                        except:
                            pass
                    
                    # Prepare template data with recipient info
                    template_data = {
                        'name': custom_data.get('name', ''),
                        'email': recipient.email,
                        **custom_data  # Include all custom data as template variables
                    }
                    
                    # Replace template variables in HTML content
                    body_html = campaign.body_html
                    for key, value in template_data.items():
                        placeholder = "{{" + key + "}}"
                        body_html = body_html.replace(placeholder, str(value))
                    
                    # Send the email
                    email_service.send_email(
                        recipient=recipient.email,
                        subject=campaign.subject,
                        body_html=body_html,
                        body_text=campaign.body_text,
                        campaign_id=campaign.id,
                        recipient_id=recipient.id
                    )
                    
                    # Update recipient status
                    recipient.status = 'sent'
                    db.session.commit()
                    count += 1
                    
                except Exception as e:
                    app.logger.error(f"Error sending to {recipient.email}: {str(e)}")
                    recipient.status = 'failed'
                    recipient.error_message = str(e)
                    db.session.commit()
        
        return count

    # Enable scheduler in the web process if configured
    if os.environ.get('SCHEDULER_ENABLED', 'false').lower() == 'true':
        app.logger.info("Initializing scheduler in web process")
        with app.app_context():
            scheduler = app.get_scheduler()
            scheduler.init_scheduler(app)
            app.logger.info(f"Scheduler initialized and running: {scheduler.scheduler.running}")
            
            # Add SQS processing job if enabled
            if app.config.get('SQS_ENABLED', False):
                app.logger.info("Setting up scheduled SQS queue processing job")
                
                # Set up the scheduled job using the function from sqs_jobs module
                # This avoids serialization issues with APScheduler
                scheduler.scheduler.add_job(
                    func=sqs_jobs.process_sqs_queue_job,  # Reference the function from the sqs_jobs module
                    trigger='interval', 
                    seconds=60, 
                    id='process_sqs_queue',
                    replace_existing=True
                )
    
    # Error handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('error.html', error_code=404, message="Page not found"), 404
        
    @app.errorhandler(500)
    def server_error(e):
        return render_template('error.html', error_code=500, message="Internal server error"), 500
    
    # Create database tables if they don't exist
    with app.app_context():
        db.create_all()
    
    return app

# Function to get the application instance - used by standalone scripts
def get_app():
    """
    Get the application instance.
    
    Used by scripts that need to access the Flask application outside of the 
    normal request flow, such as background jobs.
    
    Returns:
        Flask application instance
    """
    return create_app()

# SQS processing job is now imported from sqs_jobs.py
# This avoids serialization issues with APScheduler

# SQS processing job is now imported from sqs_jobs.py
# This avoids serialization issues with APScheduler

app = get_app()

# Initialize scheduler when app is created
with app.app_context():
    scheduler = app.get_scheduler()
    # Make sure scheduler is running
    if scheduler.scheduler and not scheduler.scheduler.running:
        scheduler.init_scheduler(app)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
