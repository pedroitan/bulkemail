#!/bin/bash
# Script to connect to Render Postgres database and apply schema updates

# Database credentials from Render
PGHOST="dpg-cvkr26p5pdvs73damd7g-a"
PGDATABASE="emailbulk_db"
PGUSER="emailbulk_db_user"
PGPASSWORD="Kq5jBzxyqMRyoNXEYkF0NvADT60YZJ1a"

# Display connection information
echo "Connecting to Render PostgreSQL database:"
echo "  Host: $PGHOST"
echo "  Database: $PGDATABASE"
echo "  User: $PGUSER"
echo ""

# Connect to the database and run the SQL
echo "Connecting to the database and applying schema updates..."
PGPASSWORD=$PGPASSWORD psql -h $PGHOST -U $PGUSER -d $PGDATABASE << EOF
-- Add missing columns to email_campaign table
ALTER TABLE email_campaign ADD COLUMN IF NOT EXISTS total_recipients INTEGER DEFAULT 0;
ALTER TABLE email_campaign ADD COLUMN IF NOT EXISTS last_segment_position INTEGER DEFAULT 0;
ALTER TABLE email_campaign ADD COLUMN IF NOT EXISTS next_segment_time TIMESTAMP;

-- Verify the columns were added
SELECT column_name 
FROM information_schema.columns 
WHERE table_name = 'email_campaign' AND 
      column_name IN ('total_recipients', 'last_segment_position', 'next_segment_time');
EOF

echo "Schema update complete!"
