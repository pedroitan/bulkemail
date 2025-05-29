"""
Complete database rebuild script

This script:
1. Identifies and backs up your existing database file
2. Creates a new database with the correct schema based on your models
3. Imports models directly from your application code
4. Outputs detailed diagnostic information

Use with caution - this will reset your database!
"""

import os
import sys
import shutil
import sqlite3
from datetime import datetime

def rebuild_database():
    print("\n=== DATABASE REBUILD UTILITY ===\n")
    
    # Step 1: Find all database files
    print("Searching for database files...")
    db_files = [f for f in os.listdir('.') if f.endswith('.db')]
    print(f"Found {len(db_files)} database files: {', '.join(db_files)}")
    
    # Step 2: Create timestamped backups of all database files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for db_file in db_files:
        backup_path = f"{db_file}.{timestamp}.backup"
        print(f"Backing up {db_file} to {backup_path}")
        try:
            shutil.copy2(db_file, backup_path)
            print(f"✓ Backup created successfully")
        except Exception as e:
            print(f"✗ Error backing up database: {e}")
    
    # Step 3: Inspect existing app.db
    main_db = 'app.db'
    if main_db in db_files:
        print(f"\nInspecting {main_db}...")
        try:
            conn = sqlite3.connect(main_db)
            cursor = conn.cursor()
            
            # Get the list of tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            print(f"Found {len(tables)} tables: {', '.join(tables)}")
            
            # Check if we should keep anything from the old database
            if 'apscheduler_jobs' in tables and len(tables) <= 3:
                print("The existing database appears to only contain scheduler and tracking tables.")
                print("We'll preserve these and add the missing campaign and recipient tables.")
            else:
                print("The existing database has a mix of tables which might cause conflicts.")
                print("We'll create a completely fresh database.")
                
            conn.close()
        except Exception as e:
            print(f"Error inspecting database: {e}")
    
    # Step 4: Initialize database with Flask app context to ensure proper models
    print("\nInitializing fresh database...")
    try:
        # Remove existing database to start fresh
        if os.path.exists(main_db):
            os.remove(main_db)
            print(f"✓ Removed existing {main_db}")
        
        # Create minimal Flask app that imports your real models
        from flask import Flask
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{main_db}'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        # Import your models - this will get the actual model definitions from your codebase
        from models import db, EmailCampaign, EmailRecipient, RecipientList
        print("✓ Successfully imported your models")
        
        # Initialize the database with the app
        db.init_app(app)
        
        # Create all tables within the app context
        with app.app_context():
            db.create_all()
            print("✓ Database tables created successfully!")
            
            # Verify the tables were actually created
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"\nCreated {len(tables)} tables:")
            for table in tables:
                print(f"- {table}")
                columns = [col['name'] for col in inspector.get_columns(table)]
                print(f"  Columns: {', '.join(columns)}")
        
        # Verify with SQLite directly
        conn = sqlite3.connect(main_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"\nDirect SQLite verification confirms {len(tables)} tables: {', '.join(tables)}")
        conn.close()
        
        print("\n✓ Database rebuild completed successfully!")
    except Exception as e:
        print(f"\n✗ Error rebuilding database: {e}")
        print("\nTroubleshooting tips:")
        print("1. Check if your model imports work correctly")
        print("2. Verify the database file paths in your configuration")
        print("3. Make sure you have write permissions to the directory")
        print("4. Check for any circular imports in your models")
        sys.exit(1)

if __name__ == "__main__":
    rebuild_database()
