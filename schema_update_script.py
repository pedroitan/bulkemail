#!/usr/bin/env python3
"""
Direct database schema update script for adding missing columns to the email_campaign table.
This is a standalone script that can be copy-pasted into the Render console.
"""

# Import only standard library modules for maximum compatibility
import os
import sys
import psycopg2
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get the DATABASE_URL from environment
DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    logger.error("DATABASE_URL environment variable is not set")
    sys.exit(1)

def execute_schema_update():
    """Execute the schema update to add missing columns"""
    try:
        logger.info(f"Connecting to database...")
        
        # Extract database parameters from the URL
        # Format is typically: postgres://username:password@host:port/database
        # Strip the protocol part
        db_url = DATABASE_URL.replace('postgres://', '')
        
        # Split into credentials and host parts
        if '@' in db_url:
            creds, url = db_url.split('@')
            username, password = creds.split(':')
            host_port, dbname = url.split('/')
            
            # Handle port if present
            if ':' in host_port:
                host, port = host_port.split(':')
            else:
                host, port = host_port, '5432'
        else:
            logger.error("Invalid DATABASE_URL format")
            return False
        
        # Connect to the database
        conn = psycopg2.connect(
            dbname=dbname,
            user=username,
            password=password,
            host=host,
            port=port
        )
        
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
        logger.info(f"Found {len(existing_columns)} existing columns")
        
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
