"""
Populate AWS Usage Dashboard with Sample Data

This script adds realistic sample data to make your AWS usage dashboard
functional immediately, even before connecting to CloudWatch.
"""

import os
import sys
import datetime
import logging
from flask import Flask

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('AWS-Initializer')

# Create a minimal Flask app for database context
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///campaigns.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

def populate_aws_usage():
    """Add sample AWS usage data to the dashboard"""
    # Import after app creation to ensure app context
    from models import db
    from aws_usage_model import AWSUsageStats
    db.init_app(app)
    
    with app.app_context():
        # Get today's date
        today = datetime.datetime.now().date()
        
        # Check if we already have data for today
        try:
            # Delete existing zero records to start fresh
            logger.info("Cleaning up any existing zero-value records...")
            existing_stats = AWSUsageStats.query.filter_by(date=today).first()
            if existing_stats and existing_stats.emails_sent_count == 0:
                db.session.delete(existing_stats)
                db.session.commit()
        except Exception as e:
            logger.error(f"Error cleaning up existing records: {str(e)}")
        
        # Create new sample data directly with SQL to avoid model inconsistencies
        try:
            logger.info("Adding sample AWS usage data...")
            conn = db.engine.connect()
            
            # Sample data - simulates 80-90% usage of AWS Free Tier
            # This data reflects what realistic usage might look like
            tx = conn.begin()
            
            # First create today's record with active campaign data
            conn.execute("""
            INSERT INTO aws_usage_stats 
            (date, emails_sent_count, emails_delivered_count, emails_bounced_count, 
            emails_complained_count, sns_notifications_count, sqs_messages_processed_count, 
            created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """, (
                today.isoformat(),  # Current date
                2644,      # ~88% of monthly SES limit
                2565,      # ~97% delivery rate  
                53,        # ~2% bounce rate
                26,        # ~1% complaint rate
                7932,      # ~3 SNS notifications per email
                5288       # ~2 SQS messages per email
            ))
            
            # Then add historical data for the past 30 days
            # This creates a realistic usage pattern over time
            for days_ago in range(1, 31):
                past_date = today - datetime.timedelta(days=days_ago)
                
                # Scale factor creates a gradual increase in usage
                scale_factor = 1 - ((days_ago - 1) / 30)
                
                # Calculate historical values
                historical_emails = int(2644 * scale_factor * 0.95)  # 95% randomness
                historical_delivered = int(historical_emails * 0.97)
                historical_bounced = int(historical_emails * 0.02)
                historical_complained = int(historical_emails * 0.01)
                historical_sns = int(historical_emails * 3)
                historical_sqs = int(historical_emails * 2)
                
                # Insert historical record
                conn.execute("""
                INSERT INTO aws_usage_stats 
                (date, emails_sent_count, emails_delivered_count, emails_bounced_count, 
                emails_complained_count, sns_notifications_count, sqs_messages_processed_count, 
                created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """, (
                    past_date.isoformat(),
                    historical_emails,
                    historical_delivered,
                    historical_bounced,
                    historical_complained,
                    historical_sns,
                    historical_sqs
                ))
            
            tx.commit()
            logger.info("Successfully added sample AWS usage data")
            
        except Exception as e:
            logger.error(f"Error adding sample data: {str(e)}")
            try:
                tx.rollback()
            except:
                pass
                
        # Verify the data was added correctly
        try:
            stats = AWSUsageStats.query.filter_by(date=today).first()
            if stats:
                logger.info(f"Verified data: {stats.emails_sent_count} emails, {stats.sns_notifications_count} SNS notifications")
            else:
                logger.error("Failed to verify data - no records found")
        except Exception as e:
            logger.error(f"Error verifying data: {str(e)}")

if __name__ == "__main__":
    logger.info("Populating AWS usage dashboard with realistic sample data...")
    populate_aws_usage()
    logger.info("Done! Your AWS usage dashboard should now show realistic usage data.")
    logger.info("Visit http://localhost:5000/aws-usage to see the updated dashboard.")
