"""
WSGI entry point for Gunicorn.
This file provides the Flask app instance to Gunicorn in the format it expects.
"""

from app import get_app, initialize_app
from commands import register_commands

# Create and fully initialize the app instance
app = initialize_app()

# Register CLI commands - this is essential for the process_email_batch command to work
if app is not None:
    register_commands(app)
else:
    raise RuntimeError("Failed to initialize Flask application in wsgi.py")

# This variable is what Gunicorn will look for
application = app

if __name__ == '__main__':
    app.run()
