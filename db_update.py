import sqlite3
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Update the DB_PATH to the actual database file
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.db')

def execute_sql(cursor, sql, params=None):
    """Execute SQL with error handling"""
    try:
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        return True
    except sqlite3.Error as e:
        logger.error(f"SQL Error: {str(e)} for query: {sql}")
        return False

def update_database():
    """Update the database schema to include tracking and verification fields"""
    logger.info(f"Updating database at {DB_PATH}")
    
    # Make sure the database exists
    if not os.path.exists(DB_PATH):
        logger.error(f"Database file not found at {DB_PATH}")
        return False
    
    try:
        # Connect to the database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Begin transaction
        conn.execute("BEGIN TRANSACTION")
        
        # 1. Add new columns to email_recipient
        recipient_columns = [
            ("last_opened_at", "TIMESTAMP"),
            ("open_count", "INTEGER DEFAULT 0"),
            ("last_clicked_at", "TIMESTAMP"),
            ("click_count", "INTEGER DEFAULT 0"),
            ("is_verified", "BOOLEAN DEFAULT 0"),
            ("verification_result", "VARCHAR(50)"),
            ("verification_date", "TIMESTAMP")
        ]
        
        # Check existing columns first to avoid errors
        cursor.execute("PRAGMA table_info(email_recipient)")
        existing_columns = [column[1] for column in cursor.fetchall()]
        
        for column_name, column_type in recipient_columns:
            if column_name not in existing_columns:
                sql = f"ALTER TABLE email_recipient ADD COLUMN {column_name} {column_type}"
                logger.info(f"Adding column: {column_name}")
                execute_sql(cursor, sql)
        
        # 2. Add verification_status column to email_campaign
        cursor.execute("PRAGMA table_info(email_campaign)")
        existing_columns = [column[1] for column in cursor.fetchall()]
        
        if "verification_status" not in existing_columns:
            sql = "ALTER TABLE email_campaign ADD COLUMN verification_status VARCHAR(20)"
            logger.info("Adding column: verification_status to email_campaign")
            execute_sql(cursor, sql)
        
        # 3. Create email_tracking table if it doesn't exist
        sql = """
        CREATE TABLE IF NOT EXISTS email_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tracking_id VARCHAR(36) UNIQUE NOT NULL,
            email_id INTEGER,
            recipient_id INTEGER,
            tracking_type VARCHAR(10) NOT NULL,
            original_url VARCHAR(1024),
            track_count INTEGER DEFAULT 0,
            first_tracked TIMESTAMP,
            last_tracked TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (email_id) REFERENCES email_campaign(id),
            FOREIGN KEY (recipient_id) REFERENCES email_recipient(id)
        )
        """
        logger.info("Creating email_tracking table (if it doesn't exist)")
        execute_sql(cursor, sql)
        
        # 4. Create email_tracking_events table if it doesn't exist
        sql = """
        CREATE TABLE IF NOT EXISTS email_tracking_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tracking_id VARCHAR(36) NOT NULL,
            event_type VARCHAR(10) NOT NULL,
            event_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address VARCHAR(45),
            user_agent TEXT,
            FOREIGN KEY (tracking_id) REFERENCES email_tracking(tracking_id)
        )
        """
        logger.info("Creating email_tracking_events table (if it doesn't exist)")
        execute_sql(cursor, sql)
        
        # 5. Create indexes for better performance
        indexes = [
            ("idx_email_tracking_tracking_id", "email_tracking", "tracking_id"),
            ("idx_email_tracking_email_id", "email_tracking", "email_id"),
            ("idx_email_tracking_recipient_id", "email_tracking", "recipient_id"),
            ("idx_email_tracking_events_tracking_id", "email_tracking_events", "tracking_id")
        ]
        
        for index_name, table_name, column_name in indexes:
            sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}({column_name})"
            logger.info(f"Creating index: {index_name}")
            execute_sql(cursor, sql)
        
        # Commit transaction
        conn.commit()
        logger.info("Database update complete")
        return True
        
    except sqlite3.Error as e:
        logger.error(f"Database error: {str(e)}")
        if conn:
            conn.rollback()
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        if conn:
            conn.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    if update_database():
        logger.info("Database update successful")
    else:
        logger.error("Database update failed")
