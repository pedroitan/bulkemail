"""
Migration script to create the AWSUsageStats table for tracking AWS Free Tier usage

This script:
1. Creates the aws_usage_stats table
2. Adds initial record for today's date
"""

import sqlite3
import os
import sys
from datetime import datetime

def run_migration():
    print("Running migration: add_aws_usage_table.py")
    
    # Get the database path
    db_path = os.path.abspath('campaigns.db')
    print(f"Using database at: {db_path}")
    
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        sys.exit(1)
    
    # Connect to the database
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if the table already exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='aws_usage_stats'")
        if cursor.fetchone():
            print("Table aws_usage_stats already exists")
        else:
            print("Creating aws_usage_stats table...")
            
            # Create the aws_usage_stats table
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
            
            # Create today's record
            today = datetime.utcnow().date().isoformat()
            cursor.execute(
                "INSERT INTO aws_usage_stats (date) VALUES (?)",
                (today,)
            )
            
            print(f"Created aws_usage_stats table and added initial record for {today}")
            
        # Commit the changes
        conn.commit()
        print("Migration completed successfully!")
        
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
        sys.exit(1)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    run_migration()
