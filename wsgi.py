"""
WSGI entry point for Gunicorn.
This file provides the Flask app instance to Gunicorn in the format it expects.
"""

import os
import logging
from flask import Flask
from flask_babel import Babel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

# Create a direct Flask application for Render deployment
app = Flask(__name__)

# Configure app
database_url = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
# Handle old postgres:// URLs from Render
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'development-key')

# Initialize extensions
from models import db
db.init_app(app)

# Initialize translations
babel = Babel(app)

# Initialize email tracking
from email_tracking import init_tracking
from models import db
init_tracking(app, db)

# Register blueprints
from recipient_lists import recipient_lists_bp
app.register_blueprint(recipient_lists_bp, url_prefix='/recipients')

# Add a root route for health checks
@app.route('/')
def index():
    return 'Bulk Email Scheduler is running', 200

with app.app_context():
    import app_views
    # Register all routes from app_views
    app_views.register_routes(app)
    
    # Register CLI commands if needed for Render's scheduled tasks
    try:
        from commands import register_commands
        register_commands(app)
        logger.info('Registered batch processing commands for scheduled execution')
    except Exception as e:
        logger.error(f'Error registering batch processing commands: {str(e)}')

# This variable is what Gunicorn will look for
application = app

if __name__ == '__main__':
    app.run()
