"""
Temporary module to fix the 'app not defined' error in app.py for deployment.
This module defines db and other necessary components that init_db.py needs
without causing import errors.
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create a minimal Flask application for db initialization
app = Flask(__name__)

# Configure database
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize the database
db = SQLAlchemy(app)

# This function returns the app instance
def get_app():
    return app
