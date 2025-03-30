#!/usr/bin/env python3
"""
Database initialization script for Bulk Email Scheduler
This script will create all necessary database tables based on the SQLAlchemy models
"""
import os
import sys

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import get_app, db
from models import EmailCampaign, EmailRecipient

def init_db():
    """Initialize the database by creating all tables"""
    app = get_app()
    with app.app_context():
        db.create_all()
        print("Database initialized successfully!")
        
        # Check if tables were created using the modern SQLAlchemy API
        from sqlalchemy import text
        with db.engine.connect() as conn:
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = result.fetchall()
            print(f"Created tables: {', '.join([table[0] for table in tables if not table[0].startswith('sqlite_')])}")
        
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
