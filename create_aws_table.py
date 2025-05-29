"""
Create AWS Usage Stats Table

This script creates the aws_usage_stats table and populates it with sample data
to make the AWS usage dashboard functional immediately.
"""

import os
import sys
import sqlite3
import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('AWS-Table-Creator')

DB_PATH = os.path.join(os.path.dirname(__file__), 'campaigns.db')

def create_aws_usage_table():
    """Create the AWS usage stats table and populate it with sample data"""
    
    logger.info(f"Using database at: {DB_PATH}")
    
    try:
        # Connect to the SQLite database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='aws_usage_stats'")
        table_exists = cursor.fetchone() is not None
        
        if not table_exists:
            logger.info("Creating aws_usage_stats table...")
            
            # Create the table using the schema from the model
            cursor.execute('''
            CREATE TABLE aws_usage_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE UNIQUE,
                emails_sent_count INTEGER DEFAULT 0,
                emails_delivered_count INTEGER DEFAULT 0,
                emails_bounced_count INTEGER DEFAULT 0,
                emails_complained_count INTEGER DEFAULT 0,
                sns_notifications_count INTEGER DEFAULT 0,
                sqs_messages_processed_count INTEGER DEFAULT 0,
                ses_daily_limit INTEGER DEFAULT 3000,
                sns_monthly_limit INTEGER DEFAULT 100000,
                monthly_emails_sent INTEGER DEFAULT 0,
                monthly_sns_notifications INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # Add an index for faster date lookups
            cursor.execute('CREATE INDEX idx_aws_usage_date ON aws_usage_stats (date)')
            conn.commit()
            
            logger.info("Table created successfully!")
        else:
            logger.info("Table aws_usage_stats already exists")
        
        # Populate with sample data
        today = datetime.datetime.now().date()
        
        # First check if we have any non-zero data already
        cursor.execute("SELECT COUNT(*) FROM aws_usage_stats WHERE emails_sent_count > 0")
        has_data = cursor.fetchone()[0] > 0
        
        if not has_data:
            logger.info("Adding sample AWS usage data...")
            
            # Sample data - simulates 80-90% usage of AWS Free Tier
            # First create today's record with active campaign data
            cursor.execute("""
            INSERT OR REPLACE INTO aws_usage_stats 
            (date, emails_sent_count, emails_delivered_count, emails_bounced_count, 
            emails_complained_count, sns_notifications_count, sqs_messages_processed_count, 
            monthly_emails_sent, monthly_sns_notifications, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """, (
                today.isoformat(),  # Current date
                2644,      # ~88% of monthly SES limit
                2565,      # ~97% delivery rate  
                53,        # ~2% bounce rate
                26,        # ~1% complaint rate
                7932,      # ~3 SNS notifications per email
                5288,      # ~2 SQS messages per email
                2644,      # Same as emails_sent for simplicity
                7932       # Same as sns_notifications for simplicity
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
                cursor.execute("""
                INSERT OR REPLACE INTO aws_usage_stats 
                (date, emails_sent_count, emails_delivered_count, emails_bounced_count, 
                emails_complained_count, sns_notifications_count, sqs_messages_processed_count,
                monthly_emails_sent, monthly_sns_notifications, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """, (
                    past_date.isoformat(),
                    historical_emails,
                    historical_delivered,
                    historical_bounced,
                    historical_complained,
                    historical_sns,
                    historical_sqs,
                    historical_emails,
                    historical_sns
                ))
            
            conn.commit()
            logger.info("Successfully added sample AWS usage data")
        else:
            logger.info("Database already contains non-zero AWS usage data, skipping sample data insertion")
            
        # Verify the data was added correctly
        cursor.execute("SELECT emails_sent_count, sns_notifications_count FROM aws_usage_stats WHERE date = ?", 
                      (today.isoformat(),))
        result = cursor.fetchone()
        
        if result:
            logger.info(f"Verified data: {result[0]} emails, {result[1]} SNS notifications")
        else:
            logger.error("Failed to verify data - no record found for today")
            
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        
    finally:
        # Close the connection
        conn.close()

if __name__ == "__main__":
    logger.info("Creating AWS usage stats table and adding sample data...")
    create_aws_usage_table()
    logger.info("Done! Your AWS usage dashboard should now show realistic usage data.")
    logger.info("Visit http://localhost:5000/aws-usage to see the updated dashboard.")
