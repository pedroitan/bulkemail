"""
Session manager to handle SQLAlchemy session issues
This helps prevent "not bound to a Session" errors
"""

import logging
from models import db

class SessionManager:
    """
    Manages database sessions to prevent SQLAlchemy session binding issues
    particularly important for applications running on Render's free tier
    """
    
    @staticmethod
    def get_fresh_object(model_class, object_id):
        """
        Get a fresh instance of an object that's guaranteed to be bound to the current session
        """
        if not object_id:
            return None
            
        try:
            # Query using the primary key to get a fresh object
            fresh_object = model_class.query.get(object_id)
            return fresh_object
        except Exception as e:
            logging.error(f"Error fetching fresh {model_class.__name__} object: {str(e)}")
            return None
    
    @staticmethod
    def safely_commit():
        """
        Safely commit changes and handle any session errors
        """
        try:
            db.session.commit()
            return True
        except Exception as e:
            logging.error(f"Database commit error: {str(e)}")
            db.session.rollback()
            return False
    
    @staticmethod
    def reset_session():
        """
        Completely reset the database session to prevent binding issues
        """
        try:
            # Clear SQLAlchemy's identity map and detach all objects
            db.session.expire_all()
            db.session.expunge_all()
            
            # Close the session and release all connections
            db.session.close()
            db.engine.dispose()
            
            # Remove the session
            db.session.remove()
            
            return True
        except Exception as e:
            logging.error(f"Session reset error: {str(e)}")
            # Try one more time with minimal operations
            try:
                db.session.remove()
                return True
            except:
                logging.critical("Critical session reset failure")
                return False
                
    @staticmethod
    def update_object_status(model_class, object_id, status_updates):
        """
        Update an object's status fields using a fresh object
        
        Args:
            model_class: The SQLAlchemy model class
            object_id: Primary key of the object to update
            status_updates: Dict with field names and values to update
        """
        try:
            # Get a fresh instance that's bound to the current session
            obj = SessionManager.get_fresh_object(model_class, object_id)
            if not obj:
                return False
                
            # Update the fields
            for field, value in status_updates.items():
                if hasattr(obj, field):
                    setattr(obj, field, value)
            
            # Commit the changes
            return SessionManager.safely_commit()
        except Exception as e:
            logging.error(f"Error updating {model_class.__name__} {object_id}: {str(e)}")
            db.session.rollback()
            return False
