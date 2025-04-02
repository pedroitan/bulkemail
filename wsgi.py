"""
WSGI entry point for Gunicorn.
This file provides the Flask app instance to Gunicorn in the format it expects.
"""

from app import get_app

# Create the app instance
app = get_app()

# This variable is what Gunicorn will look for
application = app

if __name__ == '__main__':
    app.run()
