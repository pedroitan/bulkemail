"""Emergency patch for the upload route"""
import sys
from app import get_app, db
from models import EmailCampaign, RecipientList
from sqlalchemy.exc import OperationalError

def apply_fix():
    app = get_app()
    with app.app_context():
        # Check if the recipient_list table exists
        try:
            lists_count = RecipientList.query.count()
            print(f"Found {lists_count} recipient lists")
        except OperationalError:
            print("Creating recipient_list table...")
            # Create the table if it doesn't exist
            db.create_all()
            print("Created missing tables")
        
        # Add a simple record to fix the query
        try:
            # Check campaign exists
            campaign_id = 53  # From the error URL
            campaign = EmailCampaign.query.get(campaign_id)
            if campaign:
                print(f"Found campaign: {campaign.name}")
            else:
                print(f"Campaign ID {campaign_id} not found")
        except Exception as e:
            print(f"Error checking campaign: {str(e)}")
    
    print("\nTo fix this issue:")
    print("1. Run this script on Render to ensure database tables exist")
    print("2. Update your upload_recipients.html to handle missing recipient_lists")
    print("3. Update the upload_recipients route in app.py to pass an empty list")
    print("\nSpecific code changes:")
    print("""
    # In app.py, update the upload_recipients route:
    
    @app.route('/campaigns/<int:campaign_id>/upload', methods=['GET', 'POST'])
    def upload_recipients(campaign_id):
        # ...existing code...
        
        # Get recipient lists or provide empty list as fallback
        try:
            recipient_lists = RecipientList.query.all()
        except Exception as e:
            app.logger.error(f"Error fetching recipient lists: {str(e)}")
            recipient_lists = []
            
        return render_template('upload_recipients.html', form=form, campaign=campaign, 
                              recipient_lists=recipient_lists)
    """)

if __name__ == "__main__":
    apply_fix()
