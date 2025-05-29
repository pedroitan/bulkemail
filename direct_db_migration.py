"""
Direct database migration that bypasses SQLAlchemy to fix the session binding issues
"""

import sqlite3
import logging
import os
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def migrate_database():
    """
    Directly update the SQLite database schema and fix any campaigns in inconsistent states
    """
    try:
        # Connect to the active database
        db_path = 'campaigns.db'
        logger.info(f"Connecting to database: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. Add missing columns if they don't exist
        cursor.execute("PRAGMA table_info(email_campaign)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'total_recipients' not in column_names:
            logger.info("Adding total_recipients column")
            cursor.execute("ALTER TABLE email_campaign ADD COLUMN total_recipients INTEGER DEFAULT 0")
        
        if 'last_segment_position' not in column_names:
            logger.info("Adding last_segment_position column")
            cursor.execute("ALTER TABLE email_campaign ADD COLUMN last_segment_position INTEGER DEFAULT 0")
        
        if 'next_segment_time' not in column_names:
            logger.info("Adding next_segment_time column")
            cursor.execute("ALTER TABLE email_campaign ADD COLUMN next_segment_time TIMESTAMP DEFAULT NULL")
        
        conn.commit()
        logger.info("Schema migration complete")
        
        # 2. Fix campaigns in inconsistent states
        logger.info("Fixing campaigns in inconsistent states")
        
        # Get all campaigns that might be stuck
        cursor.execute("""
            SELECT id, status, sent_count
            FROM email_campaign
            WHERE status IN ('in_progress', 'processing', 'pending', 'segmented')
        """)
        campaigns = cursor.fetchall()
        logger.info(f"Found {len(campaigns)} campaigns to check")
        
        for campaign_id, status, sent_count in campaigns:
            # Count total recipients
            cursor.execute(f"SELECT COUNT(*) FROM email_recipient WHERE campaign_id = {campaign_id}")
            total_recipients = cursor.fetchone()[0]
            
            # Count sent recipients
            cursor.execute(f"SELECT COUNT(*) FROM email_recipient WHERE campaign_id = {campaign_id} AND status = 'sent'")
            actual_sent = cursor.fetchone()[0]
            
            # Update campaign with correct counts
            cursor.execute(f"""
                UPDATE email_campaign
                SET total_recipients = {total_recipients},
                    sent_count = {actual_sent},
                    progress_percentage = {int((actual_sent / total_recipients) * 100) if total_recipients > 0 else 0}
                WHERE id = {campaign_id}
            """)
            
            # Fix campaign status
            if actual_sent > 0 and actual_sent < total_recipients:
                # Mark as segmented if partially sent
                cursor.execute(f"""
                    UPDATE email_campaign
                    SET status = 'segmented',
                        last_segment_position = {actual_sent}
                    WHERE id = {campaign_id}
                """)
                logger.info(f"Campaign {campaign_id}: Marked as segmented at position {actual_sent}/{total_recipients}")
            elif actual_sent == total_recipients and total_recipients > 0:
                # Mark as completed if all sent
                cursor.execute(f"""
                    UPDATE email_campaign
                    SET status = 'completed'
                    WHERE id = {campaign_id}
                """)
                logger.info(f"Campaign {campaign_id}: Marked as completed ({actual_sent}/{total_recipients} sent)")
            elif actual_sent == 0:
                # Reset to pending if none sent
                cursor.execute(f"""
                    UPDATE email_campaign
                    SET status = 'pending'
                    WHERE id = {campaign_id}
                """)
                logger.info(f"Campaign {campaign_id}: Reset to pending status (0/{total_recipients} sent)")
                
        # 3. Reset any stuck recipients
        logger.info("Resetting any stuck recipients")
        cursor.execute("""
            UPDATE email_recipient
            SET status = 'pending'
            WHERE status NOT IN ('sent', 'failed', 'pending')
        """)
        
        # Commit all changes
        conn.commit()
        logger.info("Database migration and fixes completed successfully")
        
        # Close connection
        conn.close()
        return True
    
    except Exception as e:
        logger.error(f"Migration error: {str(e)}")
        return False

if __name__ == "__main__":
    success = migrate_database()
    if success:
        print("Database migration completed successfully")
    else:
        print("Database migration failed - check the logs")
        sys.exit(1)
