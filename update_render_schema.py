#!/usr/bin/env python3
"""
Script to connect to Render PostgreSQL database and add missing columns
"""

import os
import sys
import psycopg2
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# The full database URL from Render
DATABASE_URL = "postgresql://emailbulk_db_user:Kq5jBzxyqMRyoNXEYkF0NvADT60YZJ1a@dpg-cvkr26p5pdvs73damd7g-a/emailbulk_db"

def execute_schema_update():
    """Execute the schema update to add missing columns"""
    try:
        logger.info(f"Connecting to database using connection string...")
        
        # Connect to the database using the connection string
        conn = psycopg2.connect(DATABASE_URL)
        
        # Set autocommit to false for transaction control
        conn.autocommit = False
        
        # Create a cursor
        cur = conn.cursor()
        
        # Check which columns already exist
        logger.info("Checking for existing columns...")
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'email_campaign'
        """)
        
        existing_columns = [col[0] for col in cur.fetchall()]
        logger.info(f"Found {len(existing_columns)} existing columns in email_campaign table")
        
        # List of columns to add with their definitions
        columns_to_add = [
            ('total_recipients', 'INTEGER DEFAULT 0'),
            ('last_segment_position', 'INTEGER DEFAULT 0'),
            ('next_segment_time', 'TIMESTAMP')
        ]
        
        # Add missing columns
        added_columns = []
        for column_name, column_type in columns_to_add:
            if column_name.lower() not in [col.lower() for col in existing_columns]:
                logger.info(f"Adding column: {column_name}")
                sql = f"ALTER TABLE email_campaign ADD COLUMN {column_name} {column_type}"
                cur.execute(sql)
                added_columns.append(column_name)
            else:
                logger.info(f"Column {column_name} already exists, skipping")
        
        # Commit the transaction
        conn.commit()
        logger.info(f"Schema update completed successfully. Added columns: {added_columns}")
        
        # Check that columns were added successfully
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'email_campaign' AND 
                column_name IN ('total_recipients', 'last_segment_position', 'next_segment_time')
        """)
        
        updated_columns = [col[0] for col in cur.fetchall()]
        logger.info(f"Verified columns now in database: {updated_columns}")
        
        # Close the connection
        cur.close()
        conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"Error updating schema: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("Starting schema update process...")
    success = execute_schema_update()
    
    if success:
        logger.info("Schema update completed successfully!")
        sys.exit(0)
    else:
        logger.error("Schema update failed!")
        sys.exit(1)
