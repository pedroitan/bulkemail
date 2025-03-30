"""
Background scheduler process for Render worker

This script initializes the Flask application and starts
the email scheduler for processing background tasks.
"""

from app import get_app
import logging
import time
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the application
app = get_app()

# Initialize scheduler with the app context
with app.app_context():
    logger.info("Starting Email Scheduler worker process")
    
    # Get scheduler instance using the lazy initialization pattern
    scheduler = app.get_scheduler()
    
    # Initialize the scheduler if needed - this respects the lazy initialization pattern
    if not scheduler.scheduler or not scheduler.scheduler.running:
        scheduler.init_scheduler(app)
    
    logger.info(f"Scheduler initialized and running: {scheduler.scheduler.running}")
    
    # Keep the process running
    try:
        while True:
            time.sleep(60)
            logger.info("Scheduler heartbeat - checking for queued email campaigns")
    except KeyboardInterrupt:
        logger.info("Scheduler worker shutting down")
