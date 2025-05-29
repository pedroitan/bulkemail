"""
Migration script to add real-time progress tracking fields to EmailCampaign model
"""
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, DateTime
import os

# Get database URI from environment or use default
db_uri = os.environ.get('DATABASE_URL', 'sqlite:///app.db')

def upgrade():
    # Connect to the database
    engine = create_engine(db_uri)
    meta = MetaData(bind=engine)
    
    # Reflect the existing table
    email_campaign = Table('email_campaign', meta, autoload=True)
    
    # Check if the columns already exist and add them if they don't
    if 'completed_at' not in email_campaign.columns:
        engine.execute('ALTER TABLE email_campaign ADD COLUMN completed_at TIMESTAMP')
    
    if 'sent_count' not in email_campaign.columns:
        engine.execute('ALTER TABLE email_campaign ADD COLUMN sent_count INTEGER DEFAULT 0')
    
    if 'total_processed' not in email_campaign.columns:
        engine.execute('ALTER TABLE email_campaign ADD COLUMN total_processed INTEGER DEFAULT 0')
    
    if 'progress_percentage' not in email_campaign.columns:
        engine.execute('ALTER TABLE email_campaign ADD COLUMN progress_percentage INTEGER DEFAULT 0')
    
    print("Added real-time progress tracking fields to EmailCampaign table")

if __name__ == '__main__':
    upgrade()
