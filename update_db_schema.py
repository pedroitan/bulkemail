import os
import sys
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create a minimal Flask application
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

def execute_sql(sql, params=None):
    """Execute SQL with error handling"""
    try:
        if params:
            db.session.execute(text(sql), params)
        else:
            db.session.execute(text(sql))
        return True
    except Exception as e:
        logger.error(f"SQL Error: {str(e)} for query: {sql}")
        return False

def update_schema():
    """Update the database schema to include tracking and verification fields"""
    logger.info("Updating database schema...")
    
    with app.app_context():
        try:
            # Begin transaction
            db.session.begin()
            
            # 1. Update email_recipient table
            columns_to_add = {
                "open_count": "INTEGER DEFAULT 0",
                "click_count": "INTEGER DEFAULT 0",
                "last_opened_at": "TIMESTAMP",
                "last_clicked_at": "TIMESTAMP",
                "is_verified": "BOOLEAN DEFAULT 0",
                "verification_result": "VARCHAR(50)",
                "verification_date": "TIMESTAMP"
            }
            
            # Get existing columns
            result = db.session.execute(text("PRAGMA table_info(email_recipient)"))
            existing_columns = [row[1] for row in result.fetchall()]
            logger.info(f"Existing columns in email_recipient: {existing_columns}")
            
            # Add missing columns
            for column_name, column_type in columns_to_add.items():
                if column_name not in existing_columns:
                    sql = f"ALTER TABLE email_recipient ADD COLUMN {column_name} {column_type}"
                    logger.info(f"Adding column: {column_name}")
                    if not execute_sql(sql):
                        raise Exception(f"Failed to add column {column_name}")
                else:
                    logger.info(f"Column {column_name} already exists")
            
            # 2. Update email_campaign table
            result = db.session.execute(text("PRAGMA table_info(email_campaign)"))
            existing_columns = [row[1] for row in result.fetchall()]
            
            if "verification_status" not in existing_columns:
                sql = "ALTER TABLE email_campaign ADD COLUMN verification_status VARCHAR(20)"
                logger.info("Adding column: verification_status to email_campaign")
                if not execute_sql(sql):
                    raise Exception("Failed to add verification_status column")
            
            # 3. Create email_tracking table if it doesn't exist
            tables_result = db.session.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            existing_tables = [row[0] for row in tables_result.fetchall()]
            
            if "email_tracking" not in existing_tables:
                logger.info("Creating email_tracking table")
                sql = """
                CREATE TABLE email_tracking (
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
                if not execute_sql(sql):
                    raise Exception("Failed to create email_tracking table")
            
            # 4. Create email_tracking_events table if it doesn't exist
            if "email_tracking_events" not in existing_tables:
                logger.info("Creating email_tracking_events table")
                sql = """
                CREATE TABLE email_tracking_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tracking_id VARCHAR(36) NOT NULL,
                    event_type VARCHAR(10) NOT NULL,
                    event_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ip_address VARCHAR(45),
                    user_agent TEXT,
                    FOREIGN KEY (tracking_id) REFERENCES email_tracking(tracking_id)
                )
                """
                if not execute_sql(sql):
                    raise Exception("Failed to create email_tracking_events table")
            
            # Commit transaction
            db.session.commit()
            logger.info("Database schema update completed successfully")
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating schema: {str(e)}")
            return False

if __name__ == "__main__":
    try:
        if update_schema():
            logger.info("Schema update completed successfully")
            sys.exit(0)
        else:
            logger.error("Schema update failed")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)
