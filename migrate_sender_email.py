from app import get_app
from models import db, EmailCampaign
from flask import current_app

def migrate_sender_email():
    """
    Migration script to add sender_email column to the email_campaign table.
    This adds the column and populates it with default sender email for existing records.
    """
    app = get_app()
    
    with app.app_context():
        # Check if we need to add the column
        conn = db.engine.connect()
        inspector = db.inspect(db.engine)
        has_column = 'sender_email' in [col['name'] for col in inspector.get_columns('email_campaign')]
        
        if not has_column:
            print("Adding sender_email column to email_campaign table...")
            conn.execute(db.text("ALTER TABLE email_campaign ADD COLUMN sender_email VARCHAR(255)"))
            
            # Update existing records with the default sender email
            default_email = current_app.config['SENDER_EMAIL']
            if default_email:
                print(f"Updating existing campaigns with default sender email: {default_email}")
                conn.execute(
                    db.text("UPDATE email_campaign SET sender_email = :email WHERE sender_email IS NULL"),
                    {"email": default_email}
                )
            
            print("Migration completed successfully.")
        else:
            print("sender_email column already exists. No migration needed.")
        
        conn.close()

if __name__ == "__main__":
    migrate_sender_email()
