from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import json
from datetime import datetime

db = SQLAlchemy()

# Association table for many-to-many relationship between recipient lists and recipients
recipient_list_items = db.Table('recipient_list_items',
    db.Column('list_id', db.Integer, db.ForeignKey('recipient_list.id'), primary_key=True),
    db.Column('recipient_id', db.Integer, db.ForeignKey('email_recipient.id'), primary_key=True)
)

class EmailCampaign(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    body_html = db.Column(db.Text, nullable=False)
    body_text = db.Column(db.Text)
    sender_name = db.Column(db.String(100))
    sender_email = db.Column(db.String(255))  # Added sender_email field
    scheduled_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, in_progress, completed, failed
    recipients_file = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)  # When the campaign actually started running
    completed_at = db.Column(db.DateTime, nullable=True)  # When the campaign finished running
    
    # Fields for real-time progress tracking
    sent_count = db.Column(db.Integer, default=0)  # Number of successfully sent emails
    total_processed = db.Column(db.Integer, default=0)  # Total number of processed recipients
    progress_percentage = db.Column(db.Integer, default=0)  # Percentage of completion
    
    # Relationship with EmailRecipient
    recipients = db.relationship('EmailRecipient', backref='campaign', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<EmailCampaign {self.name}>'

class EmailRecipient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('email_campaign.id'), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    name = db.Column(db.String(100))
    custom_data = db.Column(db.Text)  # Stored as JSON
    status = db.Column(db.String(20), default='pending')  # pending, sent, failed
    sent_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)
    
    # New fields for bounce tracking
    message_id = db.Column(db.String(100))  # AWS SES Message ID
    delivery_status = db.Column(db.String(20))  # delivered, bounced, complained, suppressed
    bounce_type = db.Column(db.String(50))  # permanent, transient, etc.
    bounce_subtype = db.Column(db.String(50))  # e.g., undetermined, general, etc.
    bounce_time = db.Column(db.DateTime)
    bounce_diagnostic = db.Column(db.Text)  # Detailed diagnostic code
    is_test = db.Column(db.Boolean, default=False)  # Flag to identify test recipients
    
    # Global status field that persists across campaigns
    global_status = db.Column(db.String(20), default='active')  # active, bounced, complained, suppressed, unsubscribed
    
    # Add these fields to the existing EmailRecipient model
    last_opened_at = db.Column(db.DateTime)
    open_count = db.Column(db.Integer, default=0)
    last_clicked_at = db.Column(db.DateTime)
    click_count = db.Column(db.Integer, default=0)
    is_verified = db.Column(db.Boolean, default=False)
    verification_result = db.Column(db.String(50))
    verification_date = db.Column(db.DateTime)
    
    # Many-to-many relationship with RecipientList
    lists = db.relationship('RecipientList', secondary=recipient_list_items,
                           backref=db.backref('recipients', lazy='dynamic'))
    
    def set_custom_data(self, data_dict):
        self.custom_data = json.dumps(data_dict)
    
    def get_custom_data(self):
        if not self.custom_data:
            return {}
        return json.loads(self.custom_data)
    
    def __repr__(self):
        return f'<EmailRecipient {self.email}>'

# Add these new models for email tracking
class EmailTracking(db.Model):
    """Model for tracking email opens and clicks"""
    __tablename__ = 'email_tracking'
    
    id = db.Column(db.Integer, primary_key=True)
    tracking_id = db.Column(db.String(36), unique=True, nullable=False)  # UUID
    email_id = db.Column(db.Integer, db.ForeignKey('email_campaign.id'))
    recipient_id = db.Column(db.Integer, db.ForeignKey('email_recipient.id'))
    tracking_type = db.Column(db.String(10), nullable=False)  # 'open' or 'click'
    original_url = db.Column(db.String(1024))  # For click tracking
    track_count = db.Column(db.Integer, default=0)
    first_tracked = db.Column(db.DateTime)
    last_tracked = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    email = db.relationship('EmailCampaign', backref=db.backref('tracking_links', lazy=True))
    recipient = db.relationship('EmailRecipient', backref=db.backref('tracking_links', lazy=True))
    events = db.relationship('EmailTrackingEvent', backref='tracking', lazy=True)

class EmailTrackingEvent(db.Model):
    """Model for tracking individual open/click events"""
    __tablename__ = 'email_tracking_events'
    
    id = db.Column(db.Integer, primary_key=True)
    tracking_id = db.Column(db.String(36), db.ForeignKey('email_tracking.tracking_id'), nullable=False)
    event_type = db.Column(db.String(10), nullable=False)  # 'open' or 'click'
    event_time = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(45))  # IPv6 can be up to 45 chars
    user_agent = db.Column(db.Text)
    
    def __repr__(self):
        return f'<EmailTrackingEvent {self.id}: {self.event_type}>'


class RecipientList(db.Model):
    """Model for storing reusable recipient lists"""
    __tablename__ = 'recipient_list'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Statistics fields
    total_recipients = db.Column(db.Integer, default=0)
    active_recipients = db.Column(db.Integer, default=0)
    bounced_recipients = db.Column(db.Integer, default=0)
    complained_recipients = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f'<RecipientList {self.name}: {self.total_recipients} recipients>'
    
    def update_stats(self):
        """Update the statistics for this recipient list"""
        # Total count
        self.total_recipients = db.session.query(recipient_list_items).filter_by(list_id=self.id).count()
        
        # Count by status
        self.active_recipients = 0
        self.bounced_recipients = 0
        self.complained_recipients = 0
        
        for recipient in self.recipients:
            if recipient.global_status == 'active':
                self.active_recipients += 1
            elif recipient.global_status == 'bounced':
                self.bounced_recipients += 1
            elif recipient.global_status == 'complained':
                self.complained_recipients += 1
