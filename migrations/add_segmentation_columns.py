"""
Database migration script to add campaign segmentation columns
"""

import sqlite3
import os
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_db_paths():
    """Get all possible SQLite database paths used in the application"""
    # Check for possible database files
    possible_files = ['campaigns.db', 'app.db']
    existing_files = []
    
    # Check environment variable first
    db_url = os.environ.get('DATABASE_URL', '')
    if db_url and db_url.startswith('sqlite:///'):
        db_file = db_url.replace('sqlite:///', '')
        if os.path.exists(db_file):
            existing_files.append(db_file)
    
    # Check for standard database files in the current directory
    for db_file in possible_files:
        if os.path.exists(db_file):
            existing_files.append(db_file)
    
    if not existing_files:
        logger.warning("No existing database files found. Using default: campaigns.db")
        return ['campaigns.db']
    
    return existing_files

def run_migration():
    """Add segmentation columns to EmailCampaign table"""
    db_paths = get_db_paths()
    success = False
    
    for db_path in db_paths:
        logger.info(f"Attempting migration on database: {db_path}")
        
        try:
            # Connect to the SQLite database
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
        
            # Check if the columns already exist
            cursor.execute("PRAGMA table_info(email_campaign)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            # Add total_recipients column if it doesn't exist
            if 'total_recipients' not in column_names:
                logger.info("Adding total_recipients column")
                cursor.execute("ALTER TABLE email_campaign ADD COLUMN total_recipients INTEGER DEFAULT 0")
            
            # Add last_segment_position column if it doesn't exist
            if 'last_segment_position' not in column_names:
                logger.info("Adding last_segment_position column")
                cursor.execute("ALTER TABLE email_campaign ADD COLUMN last_segment_position INTEGER DEFAULT 0")
            
            # Add next_segment_time column if it doesn't exist
            if 'next_segment_time' not in column_names:
                logger.info("Adding next_segment_time column")
                cursor.execute("ALTER TABLE email_campaign ADD COLUMN next_segment_time TIMESTAMP DEFAULT NULL")
            
            # Commit the changes
            conn.commit()
            logger.info("Migration completed successfully")
            
            # Update existing campaigns to set total_recipients based on the count of recipients
            cursor.execute("""
                UPDATE email_campaign
                SET total_recipients = (
                    SELECT COUNT(*) 
                    FROM email_recipient 
                    WHERE email_recipient.campaign_id = email_campaign.id
                )
                WHERE total_recipients = 0
            """)
            conn.commit()
            logger.info("Updated total_recipients for existing campaigns")
        
            # Close the connection
            conn.close()
            logger.info(f"Migration completed successfully on {db_path}")
            success = True
        
        except sqlite3.OperationalError as e:
            if "no such table: email_campaign" in str(e):
                logger.warning(f"Database {db_path} doesn't contain the email_campaign table, trying next database")
            else:
                logger.error(f"Migration failed on {db_path}: {str(e)}")
        except Exception as e:
            logger.error(f"Migration failed on {db_path}: {str(e)}")
    
    return success

if __name__ == "__main__":
    success = run_migration()
    if success:
        print("Migration completed successfully.")
    else:
        print("Migration failed. Check the logs for details.")
