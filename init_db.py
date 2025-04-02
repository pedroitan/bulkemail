#!/usr/bin/env python3
"""
Database initialization script for Bulk Email Scheduler
This script will create all necessary database tables based on the SQLAlchemy models
"""
import os
import sys
import time
import logging
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def init_db(max_retries=5, retry_delay=3):
    """
    Initialize the database by creating all tables
    
    Args:
        max_retries: Maximum number of connection retry attempts
        retry_delay: Delay between retries in seconds
    
    Returns:
        bool: True if successful, False otherwise
    """
    logging.info("Starting database initialization...")
    
    # Import database components more safely
    try:
        # First try the temporary module if it exists
        try:
            from temp_app_fix import get_app, db
            logging.info("Using temporary app module for database initialization")
        except ImportError:
            # Fall back to carefully importing just what we need from app
            logging.info("Importing directly from app module")
            # Import db directly to avoid executing route definitions
            from models import db
            # Create a minimal app just for initialization
            from flask import Flask
            app = Flask(__name__)
            app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
            app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
            db.init_app(app)
            def get_app():
                return app
    except Exception as e:
        logging.error(f"Error importing database components: {e}")
        return False
    from models import EmailCampaign, EmailRecipient
    
    # Bypass errors in case of missing columns in the database
    logging.info("Setting up error handling for potential missing columns...")
    import sqlalchemy as sa
    from sqlalchemy.ext.declarative import declarative_base
    
    # Override the original declarative base to handle missing columns
    original_init = sa.orm.instrumentation._EventsHold.__init__
    
    def _events_hold_init(self, class_):
        original_init(self, class_)
        self.dispatch._sa_event_failed_dispatch = lambda *args, **kwargs: None
    
    sa.orm.instrumentation._EventsHold.__init__ = _events_hold_init
    
    # Get application instance
    app = get_app()
    
    # Check if we're using PostgreSQL
    db_url = os.environ.get('DATABASE_URL', '')
    is_postgres = db_url.startswith('postgresql')
    
    if is_postgres:
        logging.info("PostgreSQL detected, applying optimized initialization process...")
        
        # Extract host for logging
        try:
            parsed_url = urlparse(db_url)
            host = parsed_url.netloc.split('@')[-1].split(':')[0]
            logging.info(f"Connecting to PostgreSQL at host: {host}")
        except Exception:
            logging.info("Connecting to PostgreSQL (couldn't parse host)")
    
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # Initialize database within app context
            with app.app_context():
                logging.info(f"Attempt {retry_count + 1}/{max_retries}: Creating database tables...")
                
                # First test the connection
                if is_postgres:
                    logging.info("Testing database connection...")
                    try:
                        db.engine.connect().close()
                        logging.info("Database connection successful.")
                    except Exception as conn_error:
                        logging.error(f"Database connection failed: {conn_error}")
                        raise conn_error
                
                # Create all tables
                db.create_all()
                logging.info("Database initialized successfully!")
                
                # Verify tables were created
                try:
                    from sqlalchemy import inspect
                    inspector = inspect(db.engine)
                    tables = inspector.get_table_names()
                    logging.info(f"Created tables: {', '.join(tables)}")
                    
                    # Verify specific tables we expect
                    expected_tables = {'email_campaign', 'email_recipient'}
                    found_tables = set(t.lower() for t in tables)
                    
                    if not expected_tables.issubset(found_tables):
                        missing = expected_tables - found_tables
                        logging.warning(f"Some expected tables are missing: {missing}")
                    else:
                        logging.info("All expected tables are present.")
                        
                except Exception as e:
                    logging.warning(f"Could not verify tables due to: {e}")
                
                return True
                
        except Exception as e:
            retry_count += 1
            logging.error(f"Attempt {retry_count}/{max_retries} failed: {str(e)}")
            
            if retry_count >= max_retries:
                logging.error("Maximum retry attempts reached. Database initialization failed.")
                logging.error(f"Final error: {str(e)}")
                return False
            
            logging.info(f"Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
            # Increase delay for subsequent retries
            retry_delay = min(retry_delay * 2, 30)  # Exponential backoff up to 30 seconds

def reset_db():
    """Reset the database by dropping and recreating all tables"""
    # Import database components more safely
    try:
        # First try the temporary module if it exists
        try:
            from temp_app_fix import get_app, db
            logging.info("Using temporary app module for database initialization")
        except ImportError:
            # Fall back to carefully importing just what we need from app
            logging.info("Importing directly from app module")
            # Import db directly to avoid executing route definitions
            from models import db
            # Create a minimal app just for initialization
            from flask import Flask
            app = Flask(__name__)
            app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
            app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
            db.init_app(app)
            def get_app():
                return app
    except Exception as e:
        logging.error(f"Error importing database components: {e}")
        return False
    
    app = get_app()
    with app.app_context():
        confirm = input("This will delete all data in the database. Are you sure? (y/n): ")
        if confirm.lower() not in ['y', 'yes']:
            print("Operation cancelled.")
            return False
        
        logging.info("Dropping all tables...")
        db.drop_all()
        logging.info("Creating all tables...")
        db.create_all()
        logging.info("Database reset successfully!")
        return True

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Initialize or reset the database')
    parser.add_argument('--reset', action='store_true', help='Reset the database (drops all tables)')
    parser.add_argument('--retries', type=int, default=5, help='Maximum number of retry attempts')
    parser.add_argument('--delay', type=int, default=3, help='Initial delay between retries in seconds')
    
    args = parser.parse_args()
    
    if args.reset:
        reset_db()
    else:
        success = init_db(max_retries=args.retries, retry_delay=args.delay)
        sys.exit(0 if success else 1)  # Return code based on success
