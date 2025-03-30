#!/usr/bin/env python
"""
Database migration script to add bounce tracking fields to EmailRecipient.
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
        columns_info = db.inspect(db.engine).get_columns('email_recipient')
        columns = [column['name'] for column in columns_info]
        
        # Add the new columns if they don't exist
        with db.engine.begin() as conn:
            if 'message_id' not in columns:
                conn.execute(db.text('ALTER TABLE email_recipient ADD COLUMN message_id VARCHAR(100)'))
                print("Added message_id column")
            
            if 'delivery_status' not in columns:
                conn.execute(db.text('ALTER TABLE email_recipient ADD COLUMN delivery_status VARCHAR(20)'))
                print("Added delivery_status column")
                
            if 'bounce_type' not in columns:
                conn.execute(db.text('ALTER TABLE email_recipient ADD COLUMN bounce_type VARCHAR(50)'))
                print("Added bounce_type column")
                
            if 'bounce_subtype' not in columns:
                conn.execute(db.text('ALTER TABLE email_recipient ADD COLUMN bounce_subtype VARCHAR(50)'))
                print("Added bounce_subtype column")
                
            if 'bounce_time' not in columns:
                conn.execute(db.text('ALTER TABLE email_recipient ADD COLUMN bounce_time TIMESTAMP'))
                print("Added bounce_time column")
                
            if 'bounce_diagnostic' not in columns:
                conn.execute(db.text('ALTER TABLE email_recipient ADD COLUMN bounce_diagnostic TEXT'))
                print("Added bounce_diagnostic column")
        
        print("Migration completed successfully")

if __name__ == '__main__':
    run_migration()
