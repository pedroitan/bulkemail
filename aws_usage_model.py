"""
AWS Usage Tracking Model

This module defines the model for tracking AWS Free Tier usage including:
- Emails sent (SES)
- SNS Notifications received
- SQS Messages processed

It helps monitor usage to avoid exceeding free tier limits.
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from models import db

class AWSUsageStats(db.Model):
    """Model for tracking AWS service usage metrics to monitor free tier limits"""
    __tablename__ = 'aws_usage_stats'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=datetime.utcnow().date, unique=True)
    
    # Email metrics
    emails_sent_count = db.Column(db.Integer, default=0)
    emails_delivered_count = db.Column(db.Integer, default=0)
    emails_bounced_count = db.Column(db.Integer, default=0)
    emails_complained_count = db.Column(db.Integer, default=0)
    
    # AWS service metrics
    sns_notifications_count = db.Column(db.Integer, default=0)
    sqs_messages_processed_count = db.Column(db.Integer, default=0)
    
    # Free tier limits
    ses_daily_limit = db.Column(db.Integer, default=3000)  # AWS Free Tier SES limit
    sns_monthly_limit = db.Column(db.Integer, default=100000)  # AWS Free Tier SNS limit
    
    # Monthly totals (updated daily)
    monthly_emails_sent = db.Column(db.Integer, default=0)
    monthly_sns_notifications = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @classmethod
    def get_or_create_today(cls):
        """Get today's stats record or create it if it doesn't exist"""
        today = datetime.utcnow().date()
        stats = cls.query.filter_by(date=today).first()
        
        if not stats:
            stats = cls(date=today)
            db.session.add(stats)
            db.session.commit()
            
        return stats
    
    @classmethod
    def increment_email_sent(cls):
        """Increment the emails sent counter"""
        stats = cls.get_or_create_today()
        stats.emails_sent_count += 1
        stats.monthly_emails_sent += 1
        db.session.commit()
        return stats
        
    @classmethod
    def increment_sns_notification(cls):
        """Increment the SNS notifications counter"""
        stats = cls.get_or_create_today()
        stats.sns_notifications_count += 1
        stats.monthly_sns_notifications += 1
        db.session.commit()
        return stats
        
    @classmethod
    def increment_sqs_message_processed(cls):
        """Increment the SQS messages processed counter"""
        stats = cls.get_or_create_today()
        stats.sqs_messages_processed_count += 1
        db.session.commit()
        return stats
    
    @classmethod
    def get_monthly_usage(cls, force_recalculate=False):
        """Get the current month's usage statistics
        
        Args:
            force_recalculate (bool): If True, bypasses any caching and performs 
                                     a direct database query for real-time data
        """
        current_month = datetime.utcnow().month
        current_year = datetime.utcnow().year
        
        if force_recalculate:
            # Use direct SQL query instead of ORM to bypass any caching layers
            # This is important when working with our token bucket rate limiter
            # which throttles requests but needs to show accurate data
            from sqlalchemy import text
            query = text("""
                SELECT 
                    SUM(emails_sent_count) as email_total,
                    SUM(sns_notifications_count) as sns_total,
                    SUM(sqs_messages_processed_count) as sqs_total
                FROM aws_usage_stats 
                WHERE 
                    CAST(strftime('%m', date) AS INTEGER) = :month AND
                    CAST(strftime('%Y', date) AS INTEGER) = :year
            """)
            
            # Execute direct SQL query
            result = db.session.execute(query, {"month": current_month, "year": current_year}).fetchone()
            
            # Get results (or default to 0 if None)
            email_total = result.email_total or 0
            sns_total = result.sns_total or 0
            sqs_total = result.sqs_total or 0
        else:
            # Standard ORM query (but the session should be expired before calling this)
            monthly_stats = cls.query.filter(
                db.extract('month', cls.date) == current_month,
                db.extract('year', cls.date) == current_year
            ).all()
            
            # Calculate totals
            email_total = sum(stats.emails_sent_count for stats in monthly_stats)
            sns_total = sum(stats.sns_notifications_count for stats in monthly_stats)
            sqs_total = sum(stats.sqs_messages_processed_count for stats in monthly_stats)
        
        return {
            'email_total': email_total,
            'sns_total': sns_total,
            'sqs_total': sqs_total,
            'email_percent': min(100, round((email_total / 3000) * 100, 1)),
            'sns_percent': min(100, round((sns_total / 100000) * 100, 1))
        }
    
    def __repr__(self):
        return f"<AWSUsageStats for {self.date}: {self.emails_sent_count} emails, {self.sns_notifications_count} SNS notifications>"
