"""
Database initialization script

This script initializes a fresh database with all the tables defined in your models.
It will create a new database file if it doesn't exist, or recreate all tables if it does.
"""

import os
import sys
from flask import Flask
from models import db, EmailCampaign, EmailRecipient, RecipientList, EmailTracking, EmailTrackingEvent

def initialize_database():
    print("Initializing database...")
    
    # Create a minimal Flask app
    app = Flask(__name__)
    
    # Configure the database URI - use the same as in your main app
    db_path = 'app.db'
    if os.path.exists(db_path):
        # Backup the existing database just in case
        backup_path = f"{db_path}.backup"
        print(f"Backing up existing database to {backup_path}")
        try:
            with open(db_path, 'rb') as src, open(backup_path, 'wb') as dst:
                dst.write(src.read())
        except Exception as e:
            print(f"Error backing up database: {e}")
            # Continue anyway
    
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize the database with the app
    db.init_app(app)
    
    # Create all tables within the app context
    with app.app_context():
        print("Creating all database tables...")
        db.create_all()
        print("Database tables created successfully!")
        
        # Print the created tables
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print("\nCreated tables:")
        for table in tables:
            print(f"- {table}")
            columns = [col['name'] for col in inspector.get_columns(table)]
            print(f"  Columns: {', '.join(columns)}")
    
    print("\nDatabase initialization complete!")

if __name__ == "__main__":
    initialize_database()
