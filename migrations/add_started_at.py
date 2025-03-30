#!/usr/bin/env python
"""
Database migration script to add started_at field to EmailCampaign.
Run this script with Flask app context to update the database.
"""
import sys
import os
from flask import Flask
from dotenv import load_dotenv

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Load environment variables
load_dotenv()

from models import db

def run_migration():
    # Get Flask app
    from app import create_app
    app = create_app()
    
    with app.app_context():
        # Check if columns already exist
        columns_info = db.inspect(db.engine).get_columns('email_campaign')
        columns = [column['name'] for column in columns_info]
        
        # Add the new column if it doesn't exist
        with db.engine.begin() as conn:
            if 'started_at' not in columns:
                conn.execute(db.text('ALTER TABLE email_campaign ADD COLUMN started_at TIMESTAMP'))
                print("Added started_at column to email_campaign table")
            else:
                print("started_at column already exists in email_campaign table")
                
        print("Migration completed successfully")

if __name__ == '__main__':
    run_migration()
