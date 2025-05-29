"""
Fix campaigns that might be in an inconsistent state and ensure database structure is correct
"""

import os
import sqlite3
import logging
import sys
from datetime import datetime
from flask import Flask
from models import db, EmailCampaign, EmailRecipient

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Setup Flask app context for database operations
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'development-key')
# Force use of campaigns.db regardless of environment variable
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///campaigns.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def ensure_database_columns():
    """Add segmentation columns if they don't exist"""
    try:
        # Determine database path
        db_url = app.config['SQLALCHEMY_DATABASE_URI']
        if db_url.startswith('sqlite:///'):
            db_path = db_url.replace('sqlite:///', '')
        else:
            logger.error(f"Unsupported database URL: {db_url}")
            return False

        # Connect to the SQLite database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check for required columns
        cursor.execute("PRAGMA table_info(email_campaign)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        # Add required columns if missing
        added_columns = []
        
        if 'total_recipients' not in column_names:
            logger.info("Adding total_recipients column")
            cursor.execute("ALTER TABLE email_campaign ADD COLUMN total_recipients INTEGER DEFAULT 0")
            added_columns.append('total_recipients')
            
        if 'last_segment_position' not in column_names:
            logger.info("Adding last_segment_position column")
            cursor.execute("ALTER TABLE email_campaign ADD COLUMN last_segment_position INTEGER DEFAULT 0")
            added_columns.append('last_segment_position')
            
        if 'next_segment_time' not in column_names:
            logger.info("Adding next_segment_time column")
            cursor.execute("ALTER TABLE email_campaign ADD COLUMN next_segment_time TIMESTAMP DEFAULT NULL")
            added_columns.append('next_segment_time')
            
        conn.commit()
        
        # Report results
        if added_columns:
            logger.info(f"Added the following columns: {', '.join(added_columns)}")
        else:
            logger.info("All required columns already exist")
            
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Error ensuring database columns: {str(e)}")
        return False

def fix_campaigns():
    """Fix campaigns that might be stuck in inconsistent states"""
    with app.app_context():
        # Find campaigns that might be in progress or stuck
        in_progress = EmailCampaign.query.filter(EmailCampaign.status.in_(
            ['in_progress', 'processing', 'pending', 'segmented']
        )).all()
        
        logger.info(f"Found {len(in_progress)} campaigns that may need fixing")
        
        for campaign in in_progress:
            # Count recipients for accurate stats
            total = EmailRecipient.query.filter_by(campaign_id=campaign.id).count()
            sent = EmailRecipient.query.filter_by(campaign_id=campaign.id, status='sent').count()
            
            # Update the campaign with accurate counts
            campaign.total_recipients = total
            
            # Fix progress percentage
            if total > 0:
                campaign.progress_percentage = int((sent / total) * 100)
            else:
                campaign.progress_percentage = 0
                
            # Mark as segmented if it was in progress and had sent some emails
            if sent > 0 and sent < total:
                campaign.status = 'segmented'
                campaign.last_segment_position = sent
                logger.info(f"Campaign {campaign.id}: Marked as segmented at position {sent}/{total}")
            # Mark as complete if all emails were sent
            elif sent == total and total > 0:
                campaign.status = 'completed'
                logger.info(f"Campaign {campaign.id}: Marked as completed ({sent}/{total} sent)")
            # Reset to pending if no emails were sent
            elif sent == 0:
                campaign.status = 'pending'
                logger.info(f"Campaign {campaign.id}: Reset to pending status (0/{total} sent)")
                
        # Commit changes
        db.session.commit()
        logger.info("Fixed campaigns committed to database")

if __name__ == "__main__":
    # First ensure the database structure is correct
    if not ensure_database_columns():
        logger.error("Failed to ensure database columns - aborting")
        sys.exit(1)
        
    # Then fix any campaigns in inconsistent states
    with app.app_context():
        fix_campaigns()
        
    logger.info("Campaign fixing complete")
