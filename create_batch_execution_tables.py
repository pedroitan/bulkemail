"""
Create Batch Execution Tables Migration Script

This script adds the necessary database tables and fields for batch execution
using Render's scheduled jobs. It updates the EmailCampaign model with batch
execution fields and creates the new BatchExecutionRecord table.
"""

import sys
import os
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import models but create our own Flask app
from flask import Flask
import os
from models import db, EmailCampaign

def run_migration():
    """Run the database migration to add batch execution tables."""
    # Create a minimal Flask app instance specifically for this migration
    app = Flask(__name__)
    
    # Configure database - respect DATABASE_URL environment variable if present
    database_url = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
    # Handle old postgres:// URLs from Render
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize the database with this app
    db.init_app(app)
    
    with app.app_context():
        logger.info("Starting batch execution tables migration...")
        
        # Check if the necessary columns already exist
        inspector = db.inspect(db.engine)
        email_campaign_columns = [column['name'] for column in inspector.get_columns('email_campaign')]
        
        # Create a list to track migration steps
        migration_steps = []
        
        # Add necessary columns to the email_campaign table if they don't exist
        with db.engine.begin() as conn:
            # Check for and add sender_domain if it doesn't exist
            if 'sender_domain' not in email_campaign_columns:
                conn.execute(db.text('ALTER TABLE email_campaign ADD COLUMN sender_domain VARCHAR(255)'))
                migration_steps.append("Added sender_domain column to email_campaign table")
                
            # Check for and add verification_status if it doesn't exist
            if 'verification_status' not in email_campaign_columns:
                conn.execute(db.text('ALTER TABLE email_campaign ADD COLUMN verification_status VARCHAR(20)'))
                migration_steps.append("Added verification_status column to email_campaign table")
                
            # Add batch execution fields
            if 'batch_execution_enabled' not in email_campaign_columns:
                conn.execute(db.text('ALTER TABLE email_campaign ADD COLUMN batch_execution_enabled BOOLEAN DEFAULT FALSE'))
                migration_steps.append("Added batch_execution_enabled column to email_campaign table")
                
            if 'batch_size' not in email_campaign_columns:
                conn.execute(db.text('ALTER TABLE email_campaign ADD COLUMN batch_size INTEGER DEFAULT 1000'))
                migration_steps.append("Added batch_size column to email_campaign table")
                
            if 'batch_interval_minutes' not in email_campaign_columns:
                conn.execute(db.text('ALTER TABLE email_campaign ADD COLUMN batch_interval_minutes INTEGER DEFAULT 5'))
                migration_steps.append("Added batch_interval_minutes column to email_campaign table")
                
            if 'total_batches' not in email_campaign_columns:
                conn.execute(db.text('ALTER TABLE email_campaign ADD COLUMN total_batches INTEGER DEFAULT 0'))
                migration_steps.append("Added total_batches column to email_campaign table")
                
            if 'processed_batches' not in email_campaign_columns:
                conn.execute(db.text('ALTER TABLE email_campaign ADD COLUMN processed_batches INTEGER DEFAULT 0'))
                migration_steps.append("Added processed_batches column to email_campaign table")
                
        # Check if the batch_execution_records table exists
        tables = inspector.get_table_names()
        if 'batch_execution_records' not in tables:
            # Create the BatchExecutionRecord table
            with db.engine.begin() as conn:
                conn.execute(db.text('''
                CREATE TABLE batch_execution_records (
                    id INTEGER PRIMARY KEY,
                    campaign_id INTEGER NOT NULL,
                    batch_number INTEGER NOT NULL,
                    start_index INTEGER NOT NULL,
                    batch_size INTEGER NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    scheduled_time DATETIME NOT NULL,
                    started_at DATETIME,
                    completed_at DATETIME,
                    processed_count INTEGER DEFAULT 0,
                    failed_count INTEGER DEFAULT 0,
                    error TEXT,
                    FOREIGN KEY (campaign_id) REFERENCES email_campaign (id)
                )
                '''))
                migration_steps.append("Created batch_execution_records table")
        
        # Log migration results
        if migration_steps:
            logger.info("Migration completed successfully:")
            for step in migration_steps:
                logger.info(f"  - {step}")
        else:
            logger.info("No migration steps needed, schema is already up to date.")
            
        logger.info("Batch execution tables migration finished.")

if __name__ == "__main__":
    run_migration()
