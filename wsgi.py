"""
WSGI entry point for Gunicorn.
This file provides the Flask app instance to Gunicorn in the format it expects.
"""

from app import get_app
from commands import register_commands

# Create the app instance
app = get_app()

# Register CLI commands - this is essential for the process_email_batch command to work
register_commands(app)

# This variable is what Gunicorn will look for
application = app

if __name__ == '__main__':
    app.run()
