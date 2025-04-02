#!/usr/bin/env python
"""
Direct database migration script to add the new segmentation columns to PostgreSQL database.
This is needed because we added columns to the model but didn't create a migration for them.
"""

import os
import sys
import logging
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

# Get database URL from environment or use default
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///campaigns.db')

def run_migration():
    """
    Apply the missing columns to the EmailCampaign table in PostgreSQL
    """
    try:
        logging.info(f"Connecting to database: {DATABASE_URL}")
        engine = create_engine(DATABASE_URL)
        
        # Create a connection
        with engine.connect() as connection:
            # First check if columns already exist
            column_check_queries = [
                "SELECT column_name FROM information_schema.columns WHERE table_name='email_campaign' AND column_name='total_recipients'",
                "SELECT column_name FROM information_schema.columns WHERE table_name='email_campaign' AND column_name='last_segment_position'",
                "SELECT column_name FROM information_schema.columns WHERE table_name='email_campaign' AND column_name='next_segment_time'"
            ]
            
            need_to_add_total_recipients = True
            need_to_add_last_segment_position = True
            need_to_add_next_segment_time = True
            
            for query, column_name in zip(column_check_queries, ['total_recipients', 'last_segment_position', 'next_segment_time']):
                result = connection.execute(text(query))
                if result.fetchone():
                    logging.info(f"Column {column_name} already exists, skipping")
                    if column_name == 'total_recipients':
                        need_to_add_total_recipients = False
                    elif column_name == 'last_segment_position':
                        need_to_add_last_segment_position = False
                    elif column_name == 'next_segment_time':
                        need_to_add_next_segment_time = False
            
            # Begin transaction
            transaction = connection.begin()
            
            try:
                # Add the columns if they don't exist
                if need_to_add_total_recipients:
                    logging.info("Adding total_recipients column")
                    connection.execute(text("ALTER TABLE email_campaign ADD COLUMN total_recipients INTEGER DEFAULT 0"))
                
                if need_to_add_last_segment_position:
                    logging.info("Adding last_segment_position column")
                    connection.execute(text("ALTER TABLE email_campaign ADD COLUMN last_segment_position INTEGER DEFAULT 0"))
                
                if need_to_add_next_segment_time:
                    logging.info("Adding next_segment_time column")
                    connection.execute(text("ALTER TABLE email_campaign ADD COLUMN next_segment_time TIMESTAMP"))
                
                # Commit transaction
                transaction.commit()
                logging.info("Schema update completed successfully")
            except Exception as e:
                # Rollback on error
                transaction.rollback()
                logging.error(f"Error during schema update: {str(e)}")
                raise
    except Exception as e:
        logging.error(f"Migration failed: {str(e)}")
        return False
    
    return True

if __name__ == "__main__":
    success = run_migration()
    if success:
        logging.info("Migration completed successfully")
        sys.exit(0)
    else:
        logging.error("Migration failed")
        sys.exit(1)
