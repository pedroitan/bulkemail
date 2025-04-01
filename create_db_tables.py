"""
Create Database Tables for AWS Usage Tracking

This script creates all necessary database tables for the application,
including the aws_usage_stats table needed for AWS usage tracking.
"""

import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('DB-Initializer')

# Create a minimal Flask app for database context
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///campaigns.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

def create_all_tables():
    """Create all database tables, including aws_usage_stats"""
    # Import after app creation to ensure app context
    from models import db
    # Import the AWS usage model to make sure it's registered with SQLAlchemy
    from aws_usage_model import AWSUsageStats
    
    db.init_app(app)
    
    with app.app_context():
        # Create all tables defined in the models
        logger.info("Creating all database tables...")
        db.create_all()
        logger.info("Database tables created successfully!")
        
        # Verify the aws_usage_stats table exists
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        if 'aws_usage_stats' in tables:
            logger.info("AWS usage stats table created successfully!")
            
            # Add sample data if the table is empty
            result = db.session.execute(db.select(AWSUsageStats))
            if not result.first():
                logger.info("Adding sample AWS usage data...")
                
                # Create a record for today
                stats = AWSUsageStats.get_or_create_today()
                
                # Update with sample data
                stats.emails_sent_count = 2644
                stats.emails_delivered_count = 2565
                stats.emails_bounced_count = 53
                stats.emails_complained_count = 26
                stats.sns_notifications_count = 7932
                stats.sqs_messages_processed_count = 5288
                stats.monthly_emails_sent = 2644
                stats.monthly_sns_notifications = 7932
                
                db.session.commit()
                logger.info("Sample AWS usage data added successfully!")
        else:
            logger.error("AWS usage stats table was not created!")

if __name__ == "__main__":
    logger.info("Initializing database tables...")
    create_all_tables()
    logger.info("Database initialization completed!")
