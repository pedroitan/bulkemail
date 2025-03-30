import os
import uuid
import logging
from urllib.parse import urlencode
from datetime import datetime
from flask import Blueprint, request, redirect, send_file, current_app

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create a Flask blueprint for tracking routes
tracking_bp = Blueprint('tracking', __name__)

class EmailTrackingManager:
    """
    Manages email tracking capabilities including opens and link clicks.
    
    This class implements:
    1. Open tracking via transparent 1x1 pixel images
    2. Click tracking via URL redirection
    3. Storage of tracking events in the database
    
    Uses lazy initialization pattern to work properly within Flask context.
    """
    
    def __init__(self, db, tracking_domain=None, pixel_dir=None):
        """
        Initialize the tracking manager with lazy initialization for request-dependent values.
        
        Args:
            db: SQLAlchemy database instance
            tracking_domain: Optional domain to use for tracking links (uses request.host_url if not provided)
            pixel_dir: Directory to store tracking pixel image
        """
        self.db = db
        
        # Use lazy initialization for request-dependent values
        self._tracking_domain = tracking_domain
        
        # Directory for storing tracking pixel
        self.pixel_dir = pixel_dir or os.path.join(os.path.dirname(__file__), 'static')
        
        # Ensure tracking pixel exists
        self._ensure_tracking_pixel()
    
    @property
    def tracking_domain(self):
        """
        Lazy getter for tracking domain, only accessed within request context.
        This property prevents errors when accessed outside of Flask request context.
        """
        if self._tracking_domain:
            return self._tracking_domain
        
        # Get from request context when needed
        try:
            return request.host_url.rstrip('/')
        except RuntimeError:
            # Return a placeholder if outside request context
            logger.warning("Accessing tracking_domain outside request context, using placeholder")
            return "http://localhost:5000"  
    
    def _ensure_tracking_pixel(self):
        """
        Ensure the tracking pixel exists in the static directory.
        Creates a 1x1 transparent PNG if it doesn't exist.
        """
        pixel_path = os.path.join(self.pixel_dir, 'tracking-pixel.png')
        
        if not os.path.exists(pixel_path):
            # Create a 1x1 transparent PNG
            from PIL import Image
            img = Image.new('RGBA', (1, 1), color=(0, 0, 0, 0))
            
            # Make sure the directory exists
            os.makedirs(self.pixel_dir, exist_ok=True)
            
            # Save the transparent pixel
            img.save(pixel_path, 'PNG')
            logger.info(f"Created tracking pixel at {pixel_path}")
    
    def generate_tracking_pixel(self, email_id, recipient_id):
        """
        Generate a tracking pixel URL for email opens.
        
        Args:
            email_id: ID of the email campaign
            recipient_id: ID of the recipient
            
        Returns:
            URL string to the tracking pixel that records opens
        """
        tracking_id = str(uuid.uuid4())
        
        # Store the tracking information in database
        from models import EmailTracking
        tracking = EmailTracking(
            tracking_id=tracking_id,
            email_id=email_id,
            recipient_id=recipient_id,
            tracking_type='open'
        )
        self.db.session.add(tracking)
        self.db.session.commit()
        
        # Generate tracking URL
        tracking_url = f"{self.tracking_domain}/tracking/pixel/{tracking_id}.png"
        return tracking_url
    
    def generate_tracking_link(self, email_id, recipient_id, original_url):
        """
        Generate a tracking URL for link clicks.
        
        Args:
            email_id: ID of the email campaign
            recipient_id: ID of the recipient
            original_url: The original URL that should be redirected to after tracking
            
        Returns:
            URL string that will track clicks before redirecting to original URL
        """
        tracking_id = str(uuid.uuid4())
        
        # Store the tracking information in database
        from models import EmailTracking
        tracking = EmailTracking(
            tracking_id=tracking_id,
            email_id=email_id,
            recipient_id=recipient_id,
            tracking_type='click',
            original_url=original_url
        )
        self.db.session.add(tracking)
        self.db.session.commit()
        
        # Generate redirect URL with tracking ID
        params = {'tid': tracking_id}
        tracking_url = f"{self.tracking_domain}/tracking/redirect?{urlencode(params)}"
        return tracking_url
    
    def process_html_content(self, html_content, email_id, recipient_id):
        """
        Process HTML content to add tracking pixels and convert links to tracking links.
        
        Args:
            html_content: Original HTML email content
            email_id: ID of the email campaign
            recipient_id: ID of the recipient
            
        Returns:
            Modified HTML with tracking pixel and tracking links
        """
        import re
        from bs4 import BeautifulSoup
        
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Add tracking pixel
        tracking_pixel_url = self.generate_tracking_pixel(email_id, recipient_id)
        pixel_tag = soup.new_tag('img', src=tracking_pixel_url, height="1", width="1", style="display:none")
        
        # Add the pixel to the end of the body
        if soup.body:
            soup.body.append(pixel_tag)
        else:
            # If no body tag, add it to the end of the HTML
            soup.append(pixel_tag)
        
        # Replace all links with tracking links
        for a_tag in soup.find_all('a', href=True):
            original_url = a_tag['href']
            tracking_url = self.generate_tracking_link(email_id, recipient_id, original_url)
            a_tag['href'] = tracking_url
        
        # Return the processed HTML
        return str(soup)
    
    def record_tracking_event(self, tracking_id, event_type, ip=None, user_agent=None):
        """
        Record a tracking event (open or click) in the database.
        
        Args:
            tracking_id: UUID of the tracking record
            event_type: Type of event ('open' or 'click')
            ip: IP address of the client (optional)
            user_agent: User agent string of the client (optional)
            
        Returns:
            The tracking record or None if not found
        """
        from models import EmailTracking, EmailTrackingEvent, EmailRecipient
        
        # Get the tracking record
        tracking = EmailTracking.query.filter_by(tracking_id=tracking_id).first()
        
        if tracking:
            # Create a new event
            event = EmailTrackingEvent(
                tracking_id=tracking_id,
                event_type=event_type,
                event_time=datetime.utcnow(),
                ip_address=ip or request.remote_addr,
                user_agent=user_agent or request.user_agent.string
            )
            self.db.session.add(event)
            
            # Update the first_tracked time if not set
            if not tracking.first_tracked:
                tracking.first_tracked = datetime.utcnow()
            
            # Update the last_tracked time
            tracking.last_tracked = datetime.utcnow()
            
            # Increment track count
            tracking.track_count += 1
            
            # Update recipient tracking statistics
            if tracking.recipient_id:
                recipient = EmailRecipient.query.get(tracking.recipient_id)
                if recipient:
                    if event_type == 'open':
                        recipient.open_count = recipient.open_count + 1 if recipient.open_count else 1
                        recipient.last_opened_at = datetime.utcnow()
                    elif event_type == 'click':
                        recipient.click_count = recipient.click_count + 1 if recipient.click_count else 1
                        recipient.last_clicked_at = datetime.utcnow()
            
            self.db.session.commit()
            
            logger.info(f"Recorded {event_type} event for tracking ID {tracking_id}")
            return tracking
        else:
            logger.warning(f"No tracking record found for ID {tracking_id}")
            return None

# Register routes for tracking
@tracking_bp.route('/pixel/<tracking_id>.png')
def tracking_pixel(tracking_id):
    """
    Handle tracking pixel requests for email opens.
    Returns a transparent 1x1 pixel while recording the open event.
    """
    # Since we have a circular import issue, get the tracking manager from current_app
    from flask import current_app
    
    # Record the open event
    current_app.tracking_manager.record_tracking_event(
        tracking_id.split('.')[0],  # Remove .png extension
        'open'
    )
    
    # Serve the tracking pixel
    return send_file(
        os.path.join(current_app.tracking_manager.pixel_dir, 'tracking-pixel.png'),
        mimetype='image/png'
    )

@tracking_bp.route('/redirect')
def tracking_redirect():
    """
    Handle tracking redirects for link clicks.
    Records the click event and redirects to the original URL.
    """
    # Get the tracking manager from current_app to avoid circular imports
    from flask import current_app
    
    # Get the tracking ID from the query parameters
    tracking_id = request.args.get('tid')
    
    if not tracking_id:
        return "Invalid tracking link", 400
    
    # Record the click event
    tracking = current_app.tracking_manager.record_tracking_event(tracking_id, 'click')
    
    if tracking and tracking.original_url:
        # Redirect to the original URL
        return redirect(tracking.original_url)
    else:
        return "Invalid tracking link", 400

def init_tracking(app, db):
    """
    Initialize the email tracking system.
    
    This function follows the lazy initialization pattern to avoid
    Flask application context issues.
    
    Args:
        app: Flask application instance
        db: SQLAlchemy database instance
        
    Returns:
        EmailTrackingManager instance
    """
    # Create tracking manager with lazy initialization
    tracking_manager = EmailTrackingManager(db)
    
    # Attach to app
    app.tracking_manager = tracking_manager
    
    # Register blueprint
    app.register_blueprint(tracking_bp, url_prefix='/tracking')
    
    logger.info("Email tracking system initialized")
    return tracking_manager
