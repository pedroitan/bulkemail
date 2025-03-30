import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # AWS Configuration
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_REGION = os.environ.get('AWS_REGION') or 'us-east-2'
    
    # Email Configuration
    SENDER_EMAIL = os.environ.get('SENDER_EMAIL')
    SENDER_DOMAINS = os.environ.get('SENDER_DOMAINS', '').split(',')
    MAX_EMAILS_PER_SECOND = int(os.environ.get('MAX_EMAILS_PER_SECOND', 10))
    SES_CONFIGURATION_SET = os.environ.get('SES_CONFIGURATION_SET')
    
    # File Upload Configuration
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}
