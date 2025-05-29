"""
Migration script to add missing columns to the email_campaign table

This script adds the following columns:
1. completed_at - When the campaign finished running
2. sent_count - Number of successfully sent emails
3. total_processed - Total number of processed recipients
4. progress_percentage - Percentage of completion
"""

import sqlite3
import os
import sys

def run_migration():
    print("Running migration: add_missing_columns.py")
    
    # Get the database path - using app.db in the root directory
    db_path = 'app.db'
    
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        print("Please check the database location and update this script.")
        sys.exit(1)
    
    print(f"Using database at: {db_path}")
    
    # Connect to the database
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if the columns already exist to avoid errors
        columns = [row[1] for row in cursor.execute("PRAGMA table_info(email_campaign)")]
        
        # Add completed_at column if it doesn't exist
        if 'completed_at' not in columns:
            print("Adding completed_at column to email_campaign table")
            cursor.execute("ALTER TABLE email_campaign ADD COLUMN completed_at TIMESTAMP")
        else:
            print("Column completed_at already exists")
            
        # Add sent_count column if it doesn't exist
        if 'sent_count' not in columns:
            print("Adding sent_count column to email_campaign table")
            cursor.execute("ALTER TABLE email_campaign ADD COLUMN sent_count INTEGER DEFAULT 0")
        else:
            print("Column sent_count already exists")
            
        # Add total_processed column if it doesn't exist
        if 'total_processed' not in columns:
            print("Adding total_processed column to email_campaign table")
            cursor.execute("ALTER TABLE email_campaign ADD COLUMN total_processed INTEGER DEFAULT 0")
        else:
            print("Column total_processed already exists")
            
        # Add progress_percentage column if it doesn't exist
        if 'progress_percentage' not in columns:
            print("Adding progress_percentage column to email_campaign table")
            cursor.execute("ALTER TABLE email_campaign ADD COLUMN progress_percentage INTEGER DEFAULT 0")
        else:
            print("Column progress_percentage already exists")
        
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
