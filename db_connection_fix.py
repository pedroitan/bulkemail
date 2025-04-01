"""
Database Connection Handler

This module implements a robust database connection handling system for Render deployment.
It provides connection pooling, timeout handling, and automatic reconnection.
"""

import os
import time
from functools import wraps
from sqlalchemy import event
from sqlalchemy.exc import OperationalError, DisconnectionError

def setup_db_engine_for_render(app, db):
    """
    Configure SQLAlchemy for more reliable operation on Render's free tier
    """
    engine = db.engine
    
    # Set a reasonable pool size for Render's free tier
    # The default can be too large and cause connection exhaustion
    engine.pool._pool.maxsize = 5
    
    # Set a shorter timeout for connections to detect stale connections faster
    engine.pool._pool.timeout = 30
    
    # Enable pool pre-ping to check connection validity before using
    @event.listens_for(engine, "engine_connect")
    def ping_connection(connection, branch):
        if branch:
            # Don't ping on checkout for "branched" connections
            return

        # Ping the connection to test if it's still valid
        try:
            connection.scalar(db.select([1]))
        except Exception:
            # Reconnect if necessary
            connection.connection.close()
            connection.connection = None
            raise DisconnectionError("Connection invalid")
    
    # Log when connections are being checked out/returned
    @event.listens_for(engine, "checkout")
    def receive_checkout(dbapi_connection, connection_record, connection_proxy):
        app.logger.debug("Connection checkout: %s", id(dbapi_connection))
    
    @event.listens_for(engine, "checkin")
    def receive_checkin(dbapi_connection, connection_record):
        app.logger.debug("Connection checkin: %s", id(dbapi_connection))
    
    # Handle disconnects gracefully
    @event.listens_for(engine, "handle_error")
    def handle_db_error(exception_context):
        app.logger.warning("Database error: %s", str(exception_context.original_exception))
    
    app.logger.info("Database connection pooling configured for Render")

def with_db_reconnect(max_retries=3, retry_delay=0.5):
    """
    Decorator for functions that need database access, with auto-reconnect on failures
    
    Example usage:
    
    @with_db_reconnect()
    def some_db_function():
        result = db.session.execute(...)
        return result
    """
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

def apply_to_app():
    """Apply all database fixes to the current app"""
    from app import get_app, db
    app = get_app()
    
    with app.app_context():
        setup_db_engine_for_render(app, db)
        app.logger.info("Applied database connection fixes for Render")

if __name__ == "__main__":
    apply_to_app()
