"""
Migration script to add missing delay columns to email_recipient table

This script adds:
1. delay_type - Type of delivery delay (e.g., 'MailboxFull', 'MessageTooLarge')
2. delay_time - Timestamp when the delay occurred
"""

import sqlite3
import os
import sys

def run_migration():
    print("Running migration: add_delay_columns.py")
    
    # Get the database path
    db_path = os.path.abspath('campaigns.db')
    print(f"Using database at: {db_path}")
    
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        sys.exit(1)
    
    # Connect to the database
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if the columns already exist to avoid errors
        columns = [row[1] for row in cursor.execute("PRAGMA table_info(email_recipient)")]
        
        # Add delay_type column if it doesn't exist
        if 'delay_type' not in columns:
            print("Adding delay_type column to email_recipient table")
            cursor.execute("ALTER TABLE email_recipient ADD COLUMN delay_type VARCHAR(50)")
        else:
            print("Column delay_type already exists")
            
        # Add delay_time column if it doesn't exist
        if 'delay_time' not in columns:
            print("Adding delay_time column to email_recipient table")
            cursor.execute("ALTER TABLE email_recipient ADD COLUMN delay_time TIMESTAMP")
        else:
            print("Column delay_time already exists")
        
        # Commit the changes
        conn.commit()
        print("Migration completed successfully!")
        
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
        sys.exit(1)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    run_migration()
