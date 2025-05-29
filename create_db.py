"""
Direct database creation script

This script:
1. Creates a database file with the correct schema
2. Forces SQLite to write to the file directly
3. Adds the progress tracking columns needed for your synchronous processing approach
"""

import os
import sqlite3
from flask import Flask
from pathlib import Path

def create_database():
    print("\n=== DIRECT DATABASE CREATION UTILITY ===\n")
    
    # Force a specific database path in the current directory
    db_file = os.path.abspath('campaigns.db')
    print(f"Creating database at: {db_file}")
    
    # Backup any existing database first
    if os.path.exists(db_file) and os.path.getsize(db_file) > 0:
        backup_file = f"{db_file}.backup"
        print(f"Backing up existing database to {backup_file}")
        try:
            with open(db_file, 'rb') as src, open(backup_file, 'wb') as dst:
                dst.write(src.read())
        except Exception as e:
            print(f"Error backing up database: {e}")
    
    # Create a minimal Flask app with absolute file path
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_file}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Import models and create all tables
    try:
        from models import db
        db.init_app(app)
        
        with app.app_context():
            db.create_all()
            print("✓ Tables created with SQLAlchemy")
        
        # Verify with direct SQLite connection
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        
        if tables:
            print(f"\nDatabase created successfully with {len(tables)} tables:")
            for table in tables:
                print(f"- {table}")
                cursor.execute(f"PRAGMA table_info({table})")
                columns = [f"{col[1]} ({col[2]})" for col in cursor.fetchall()]
                if len(columns) > 5:
                    print(f"  Columns: {', '.join(columns[:5])}...")
                else:
                    print(f"  Columns: {', '.join(columns)}")
            
            # Add missing progress tracking columns if needed
            print("\nChecking for missing progress tracking columns...")
            columns = {row[1] for row in cursor.execute("PRAGMA table_info(email_campaign)")}
            
            missing_columns = []
            if 'completed_at' not in columns:
                missing_columns.append(("completed_at", "TIMESTAMP"))
            if 'sent_count' not in columns:
                missing_columns.append(("sent_count", "INTEGER DEFAULT 0"))
            if 'total_processed' not in columns:
                missing_columns.append(("total_processed", "INTEGER DEFAULT 0"))
            if 'progress_percentage' not in columns:
                missing_columns.append(("progress_percentage", "INTEGER DEFAULT 0"))
            
            if missing_columns:
                print(f"Adding {len(missing_columns)} missing columns to support your synchronous processing approach:")
                for col_name, col_type in missing_columns:
                    print(f"- Adding column: {col_name} ({col_type})")
                    try:
                        cursor.execute(f"ALTER TABLE email_campaign ADD COLUMN {col_name} {col_type}")
                    except sqlite3.Error as e:
                        print(f"  Error adding column {col_name}: {e}")
                
                conn.commit()
                print("✓ Progress tracking columns added successfully")
            else:
                print("✓ All progress tracking columns already exist")
            
            print("\n✓ Database setup complete and verified!")
            print(f"\nConnect to this database using: sqlite:///{db_file}")
            print("Update your .env file or app configuration to use this database URL")
            
        else:
            print("❌ Database file created but no tables were found!")
            print("This may indicate a permissions issue or configuration problem.")
            
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Error creating database: {e}")
        if "cannot open database file" in str(e).lower():
            print("\nTroubleshooting:")
            print("1. Check directory permissions")
            print(f"2. Current directory: {os.getcwd()}")
            print(f"3. File path: {db_file}")
            print("4. Directory writeable:", os.access(os.path.dirname(db_file), os.W_OK))

if __name__ == "__main__":
    create_database()
