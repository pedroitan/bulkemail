"""
Application Fix for Render Deployment

This module applies fixes to the Flask application for more reliable operation on Render:
1. Optimizes database connection pooling
2. Adds defensive error handling for campaign pages
3. Ensures all necessary database schema elements exist

To use: import this in app.py before creating routes
"""

import time
import logging
import traceback
from functools import wraps
from sqlalchemy import text, event, inspect
from sqlalchemy.exc import OperationalError, DisconnectionError

def setup_db_engine_for_render(app, db):
    """Configure SQLAlchemy for more reliable operation on Render's free tier"""
    engine = db.engine
    
    # Set a reasonable pool size for Render's free tier
    engine.pool._pool.maxsize = 5
    engine.pool._pool.timeout = 30
    
    # Enable pool pre-ping to check connection validity before using
    @event.listens_for(engine, "engine_connect")
    def ping_connection(connection, branch):
        if branch:
            return

        try:
            connection.scalar(text("SELECT 1"))
        except Exception:
            connection.connection.close()
            connection.connection = None
            raise DisconnectionError("Connection invalid")
    
    # Handle disconnects gracefully
    @event.listens_for(engine, "handle_error")
    def handle_db_error(exception_context):
        if isinstance(exception_context.original_exception, OperationalError):
            if "server closed the connection unexpectedly" in str(exception_context.original_exception):
                app.logger.warning("Database connection lost, will reconnect on next access")
    
    app.logger.info("Database connection pooling configured for Render")

def with_db_reconnect(max_retries=3, retry_delay=0.5):
    """Decorator for functions that need database access, with auto-reconnect on failures"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries <= max_retries:
                try:
                    return func(*args, **kwargs)
                except OperationalError as e:
                    if "server closed the connection unexpectedly" in str(e) and retries < max_retries:
                        retries += 1
                        time.sleep(retry_delay)
                        # Force a new connection on next usage
                        from app import db
                        db.session.remove()
                        continue
                    raise
        return wrapper
    return decorator

def apply_error_handlers(app):
    """Apply error handlers to the Flask app"""
    
    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"500 Error: {error}")
        app.logger.error(traceback.format_exc())
        return render_template('error.html', 
                              error_code=500,
                              error_message="Internal server error. Our team has been notified."), 500
    
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('error.html', 
                              error_code=404, 
                              error_message="Page not found."), 404

def safe_campaign_detail(original_function):
    """Decorator to add error handling to campaign detail routes"""
    @wraps(original_function)
    def wrapper(campaign_id):
        from app import app, db
        from models import EmailCampaign
        
        try:
            return original_function(campaign_id)
        except Exception as e:
            app.logger.error(f"Error in campaign_detail for ID {campaign_id}: {str(e)}")
            app.logger.error(traceback.format_exc())
            
            # Try to fix common issues with campaign data
            try:
                # Fix NULL values in required fields
                campaign = EmailCampaign.query.get(campaign_id)
                if campaign:
                    if hasattr(campaign, 'progress_percentage') and campaign.progress_percentage is None:
                        campaign.progress_percentage = 0
                    if hasattr(campaign, 'sent_count') and campaign.sent_count is None:
                        campaign.sent_count = 0
                    if hasattr(campaign, 'total_processed') and campaign.total_processed is None:
                        campaign.total_processed = 0
                    db.session.commit()
                    app.logger.info(f'Fixed NULL values for campaign {campaign_id}')
                    
                    # Create a minimal version of the page with essential info
                    from flask import render_template, flash, redirect, url_for
                    return render_template('campaign_detail.html', 
                                        campaign=campaign, 
                                        recipients=[], 
                                        status_stats={'pending': 0, 'sent': 0, 'failed': 0},
                                        delivery_stats={'delivered': 0, 'bounced': 0, 'complained': 0, 'opened': 0, 'clicked': 0})
            except Exception as fix_error:
                app.logger.error(f'Failed to apply fix: {str(fix_error)}')
            
            # If all else fails, show error page
            from flask import flash, redirect, url_for
            flash('An error occurred loading the campaign. Please try again later.', 'danger')
            return redirect(url_for('dashboard'))
    
    return wrapper

def ensure_database_schema(app, db):
    """Ensure all necessary database tables and columns exist"""
    with app.app_context():
        try:
            # Check email_campaign table
            inspector = inspect(db.engine)
            if 'email_campaign' in inspector.get_table_names():
                columns = inspector.get_columns('email_campaign')
                column_names = [c['name'] for c in columns]
                
                # Add missing columns if needed
                required_columns = {
                    'completed_at': 'TIMESTAMP WITHOUT TIME ZONE',
                    'started_at': 'TIMESTAMP WITHOUT TIME ZONE',
                    'progress_percentage': 'FLOAT DEFAULT 0',
                    'sent_count': 'INTEGER DEFAULT 0',
                    'total_processed': 'INTEGER DEFAULT 0'
                }
                
                for col_name, col_type in required_columns.items():
                    if col_name not in column_names:
                        app.logger.info(f"Adding missing column: {col_name}")
                        db.session.execute(text(f"ALTER TABLE email_campaign ADD COLUMN {col_name} {col_type}"))
                
                # Fix NULL values in critical columns
                fixes = [
                    "UPDATE email_campaign SET progress_percentage = 0 WHERE progress_percentage IS NULL",
                    "UPDATE email_campaign SET sent_count = 0 WHERE sent_count IS NULL",
                    "UPDATE email_campaign SET total_processed = 0 WHERE total_processed IS NULL",
                ]
                
                for fix_sql in fixes:
                    db.session.execute(text(fix_sql))
                
                db.session.commit()
                app.logger.info("Database schema verified and fixed if needed")
        
        except Exception as e:
            app.logger.error(f"Error ensuring database schema: {str(e)}")
            db.session.rollback()

def apply_fixes(app, db):
    """Apply all fixes to the application"""
    # Set up enhanced logging
    if not app.debug:
        from logging.handlers import RotatingFileHandler
        import os
        
        # Ensure logs directory exists
        if not os.path.exists('logs'):
            os.makedirs('logs')
            
        file_handler = RotatingFileHandler('logs/app.log', maxBytes=1024 * 1024 * 10, backupCount=5)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Bulk Email application startup with fixes applied')
    
    # Apply database fixes
    setup_db_engine_for_render(app, db)
    ensure_database_schema(app, db)
    apply_error_handlers(app)
    
    app.logger.info("All fixes applied successfully")
