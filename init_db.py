#!/usr/bin/env python3
"""
Database initialization script for Bulk Email Scheduler
This script will create all necessary database tables based on the SQLAlchemy models
"""
import os
import sys
import time

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import get_app, db
from models import EmailCampaign, EmailRecipient

def init_db():
    """Initialize the database by creating all tables"""
    print("Starting database initialization...")
    
    # Get application instance
    app = get_app()
    
    # If we're using PostgreSQL, give it a moment to be ready
    if 'postgresql' in os.environ.get('DATABASE_URL', ''):
        print("PostgreSQL detected, waiting for 5 seconds to ensure database is ready...")
        time.sleep(5)
    
    # Initialize database within app context
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        print("Database initialized successfully!")
        
        # Check if tables were created
        try:
            from sqlalchemy import text, inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"Created tables: {', '.join(tables)}")
        except Exception as e:
            print(f"Warning: Could not verify tables due to: {e}")
        
        return True

def reset_db():
    """Reset the database by dropping and recreating all tables"""
    app = get_app()
    with app.app_context():
        confirm = input("This will delete all data in the database. Are you sure? (y/n): ")
        if confirm.lower() not in ['y', 'yes']:
            print("Operation cancelled.")
            return False
        
        db.drop_all()
        db.create_all()
        print("Database reset successfully!")
        return True

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Initialize or reset the database')
    parser.add_argument('--reset', action='store_true', help='Reset the database (drops all tables)')
    
    args = parser.parse_args()
    
    if args.reset:
        reset_db()
    else:
        init_db()
