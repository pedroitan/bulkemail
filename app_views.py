
#!/usr/bin/env python3
"""Extracted views from app.py for the Bulk Email Scheduler application
These are the main application routes."""
from flask import render_template, redirect, url_for, request, flash, jsonify, current_app
from datetime import datetime
import os
from models import db, EmailCampaign, EmailRecipient
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, DateTimeField, SelectField, BooleanField, IntegerField, SubmitField
from wtforms.validators import DataRequired, Email, Optional, Length, ValidationError

def register_routes(app):
    # Main route
    @app.route('/')
    def index():
        campaigns = EmailCampaign.query.order_by(EmailCampaign.scheduled_time.desc()).all()
        return render_template('index.html', campaigns=campaigns)
    
    @app.route('/campaigns')
    def campaigns():
        campaigns = EmailCampaign.query.order_by(EmailCampaign.scheduled_time.desc()).all()
        return render_template('campaigns.html', campaigns=campaigns)
    
    @app.route('/campaign/<int:campaign_id>')
    def campaign_detail(campaign_id):
        campaign = EmailCampaign.query.get_or_404(campaign_id)
        recipients = EmailRecipient.query.filter_by(campaign_id=campaign_id).all()
        return render_template('campaign_detail.html', campaign=campaign, recipients=recipients)
    
    # Campaign form class with all necessary fields
    class CampaignForm(FlaskForm):
        name = StringField('Campaign Name', validators=[DataRequired(), Length(max=100)])
        subject = StringField('Email Subject', validators=[DataRequired(), Length(max=200)])
        sender_name = StringField('Sender Name', validators=[DataRequired(), Length(max=100)])
        sender_email = StringField('Sender Email Username', validators=[DataRequired(), Length(max=100)]) 
        sender_domain = SelectField('Sender Email Domain', validators=[DataRequired()])
        scheduled_time = DateTimeField('Scheduled Time', format='%Y-%m-%dT%H:%M', validators=[Optional()])
        body_html = TextAreaField('Email Content (HTML)', validators=[DataRequired()])
        body_text = TextAreaField('Email Content (Plain Text)', validators=[Optional()])
        # Batch execution fields
        batch_execution_enabled = BooleanField('Enable Batch Execution', default=False)
        batch_size = IntegerField('Batch Size', default=1000, validators=[Optional()])
        batch_interval_minutes = IntegerField('Minutes Between Batches', default=5, validators=[Optional()])
        # Submit button
        submit = SubmitField('Save Campaign')
    
    @app.route('/create_campaign', methods=['GET', 'POST'])
    def create_campaign():
        """Create a new email campaign"""
        form = CampaignForm()
        
        # Populate the sender domain dropdown with verified domains
        domains = current_app.config.get('SENDER_DOMAINS', ['vendo147.com', 'example.com'])
        if domains:
            form.sender_domain.choices = [(domain, domain) for domain in domains if domain]
            # Set a default domain if available
            if 'vendo147.com' in [choice[0] for choice in form.sender_domain.choices]:
                form.sender_domain.data = 'vendo147.com'
        
        if form.validate_on_submit():
            # Create a new campaign
            campaign = EmailCampaign(
                name=form.name.data,
                subject=form.subject.data,
                sender_name=form.sender_name.data,
                sender_email=f"{form.sender_email.data}@{form.sender_domain.data}",
                body_html=form.body_html.data,
                body_text=form.body_text.data,
                scheduled_time=form.scheduled_time.data,
                status='draft',
                created_at=datetime.now(),
                batch_execution_enabled=form.batch_execution_enabled.data,
                batch_size=form.batch_size.data,
                batch_interval_minutes=form.batch_interval_minutes.data
            )
            
            # Update status based on scheduled time
            if campaign.scheduled_time and campaign.scheduled_time > datetime.now():
                campaign.status = 'scheduled'
            
            db.session.add(campaign)
            db.session.commit()
            flash('Campaign created successfully', 'success')
            return redirect(url_for('campaign_detail', campaign_id=campaign.id))
            
        return render_template('create_campaign.html', form=form)
        
    @app.route('/campaigns/<int:campaign_id>/edit', methods=['GET', 'POST'])
    def edit_campaign(campaign_id):
        """Edit an existing campaign"""
        campaign = EmailCampaign.query.get_or_404(campaign_id)
        form = CampaignForm(obj=campaign)
        
        # Populate the sender domain dropdown with verified domains
        domains = current_app.config.get('SENDER_DOMAINS', ['vendo147.com', 'example.com'])
        if domains:
            form.sender_domain.choices = [(domain, domain) for domain in domains if domain]
            
            # If this is a new form load and no sender email exists
            if not form.is_submitted() and (not campaign.sender_email or '@' not in campaign.sender_email):
                # Set a default domain
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
                campaign.status = 'draft'
        
            db.session.commit()
            flash('Campaign updated successfully', 'success')
        
            return redirect(url_for('campaign_detail', campaign_id=campaign.id))
        
        return render_template('edit_campaign.html', form=form, campaign=campaign)
    
    @app.route('/verify_recipients', methods=['GET', 'POST'])
    def verify_recipients():
        return render_template('verify_recipients.html')
    
    @app.route('/bounce_report')
    def bounce_report():
        """Show a report of all bounced emails"""
        # Get bounced emails - filter by delivery_status instead of bounce_status
        bounced_emails = EmailRecipient.query.filter_by(delivery_status='bounced').all()
        
        # Get complaint emails - filter by delivery_status
        complaint_emails = EmailRecipient.query.filter_by(delivery_status='complained').all()
        
        # Get delivery statistics
        stats = {
            'delivered': EmailRecipient.query.filter_by(delivery_status='delivered').count(),
            'bounced': len(bounced_emails),
            'complained': len(complaint_emails),
            'sent': EmailRecipient.query.filter_by(status='sent').count(),
            'total': EmailRecipient.query.count()
        }
        
        return render_template(
            'bounce_report.html',
            bounced_emails=bounced_emails,
            complaint_emails=complaint_emails,
            stats=stats
        )
    
    @app.route('/tracking_campaigns')
    def tracking_campaigns():
        return render_template('tracking_campaigns.html')
    
    @app.route('/campaigns/<int:campaign_id>/delete', methods=['POST', 'DELETE'])
    def delete_campaign(campaign_id):
        """Delete a campaign and all associated data"""
        try:
            campaign = EmailCampaign.query.get_or_404(campaign_id)
            
            # First get all recipient IDs for this campaign
            recipient_ids = [r.id for r in EmailRecipient.query.filter_by(campaign_id=campaign_id).all()]
            
            # Delete all tracking data associated with these recipients
            if recipient_ids:
                from models import EmailTracking
                # Delete tracking records referencing these recipients
                EmailTracking.query.filter(EmailTracking.recipient_id.in_(recipient_ids)).delete(synchronize_session=False)
            
            # Now delete all recipients associated with the campaign
            EmailRecipient.query.filter_by(campaign_id=campaign_id).delete()
            
            # Finally delete the campaign
            db.session.delete(campaign)
            db.session.commit()
            
            # Add flash message
            flash('Campaign deleted successfully', 'success')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error deleting campaign: {str(e)}")
            flash(f'Error deleting campaign: {str(e)}', 'danger')
    
        # Always redirect to campaigns list
        return redirect(url_for('campaigns'))
    
    @app.route('/db_status')
    def db_status():
        """Display database schema status"""
        # Check if all required columns exist in email_campaign table
        required_columns = [
            'sender_domain', 'completed_at', 'verification_status', 'sent_count',
            'total_processed', 'progress_percentage', 'batch_execution_enabled',
            'batch_size', 'batch_interval_minutes', 'total_batches', 'processed_batches'
        ]
        
        missing_columns = []
        with app.app_context():
            # Use reflection to get table info
            import sqlite3
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.db')
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(email_campaign)")
            columns = {col[1]: col for col in cursor.fetchall()}
            
            for column in required_columns:
                if column not in columns:
                    missing_columns.append(column)
            
            conn.close()
        
        return render_template('db_status.html', 
                               missing_columns=missing_columns,
                               required_columns=required_columns,
                               all_columns=list(columns.keys()) if 'columns' in locals() else [])
    
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def server_error(e):
        return render_template('error.html', error_code=500, message='Internal Server Error'), 500
