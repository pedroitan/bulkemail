from app import app
from models import EmailCampaign

with app.app_context():
    campaigns = EmailCampaign.query.all()
    print("Available campaigns:")
    for campaign in campaigns:
        print(f"ID: {campaign.id}, Name: {campaign.name}, Status: {campaign.status}")
