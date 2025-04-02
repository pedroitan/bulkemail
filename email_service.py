"""
Email Service Module

This module provides email sending functionality using Amazon SES with a lazy initialization pattern.
The SESEmailService implements a pattern that only initializes the boto3 client when needed,
preventing issues when working outside the Flask application context.
"""

import boto3
from botocore.exceptions import ClientError, WaiterError, ConnectionClosedError
import logging
import time
import random
from flask import current_app
from string import Template
import os
from dotenv import load_dotenv, find_dotenv
import uuid
import threading

# AWS SES rate limiter to prevent API throttling
class SESRateLimiter:
    """
    Rate limiter for AWS SES to prevent throttling errors
    Implements token bucket algorithm with retry logic and jitter
    """
    def __init__(self, max_send_rate=10, recovery_period=1.0):
        self.max_send_rate = max_send_rate  # Max emails per second
        self.recovery_period = recovery_period  # Time to refill one token
        self.available_tokens = max_send_rate
        self.last_refill_time = time.time()
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
    
    def wait_for_token(self, retries=5):
        """Wait until a token is available, with exponential backoff on failure"""
        retry_count = 0
        max_wait = 60  # Maximum wait time in seconds
        
        while retry_count < retries:
            with self.lock:
                self._refill_tokens()
                if self.available_tokens >= 1:
                    self.available_tokens -= 1
                    return True
                
                # Calculate wait time with exponential backoff and jitter
                if retry_count == 0:
                    wait_time = self.recovery_period
                else:
                    # Exponential backoff with jitter to prevent thundering herd
                    base_wait = min(self.recovery_period * (2 ** retry_count), max_wait)
                    wait_time = base_wait * (0.75 + random.random() * 0.5)  # 75-125% randomization
                    
                self.logger.info(f"Rate limit reached. Waiting {wait_time:.2f}s before retrying (attempt {retry_count+1}/{retries})")
            
            # Sleep outside the lock to allow other threads to proceed
            time.sleep(wait_time)
            retry_count += 1
        
        return False
    
    def _refill_tokens(self):
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill_time
        new_tokens = elapsed / self.recovery_period
        
        if new_tokens > 0:
            self.available_tokens = min(self.max_send_rate, self.available_tokens + new_tokens)
            self.last_refill_time = now

# SESEmailService class for sending emails through Amazon SES
class SESEmailService:
    """
    Amazon SES Email Service with lazy initialization pattern.
    
    This class handles email sending through Amazon SES while implementing a lazy initialization
    pattern that only creates the boto3 client when actually needed. This prevents common issues
    with Flask applications where importing modules can cause "working outside of application context"
    errors.
    
    The service supports:
    - HTML and plain text emails
    - Custom sender names and email addresses
    - AWS SES configuration sets for tracking via SNS
    - Template variable substitution
    """
    def __init__(self, aws_access_key_id=None, aws_secret_access_key=None, region_name=None):
        """
        Initialize the SESEmailService with optional AWS credentials.
        
        Note: This constructor does NOT create the boto3 client - it is only created when needed
        via the _ensure_client() method, implementing the lazy initialization pattern.
        
        Args:
            aws_access_key_id: Optional AWS access key, defaults to environment variable
            aws_secret_access_key: Optional AWS secret key, defaults to environment variable
            region_name: Optional AWS region, defaults to environment variable
        """
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.region_name = region_name
        self.client = None
        self.logger = logging.getLogger(__name__)
        self.tracking_manager = None
        self.configuration_set = None
        # Initialize sender_email to None so it gets loaded properly in _ensure_client
        self.sender_email = None
        
        # Add rate limiter for SES API calls
        # Free tier limit is ~450 emails per day or ~14 per hour
        # To stay safe, we'll limit to 10 per second with automatic throttling
        self.rate_limiter = SESRateLimiter(max_send_rate=10, recovery_period=0.1)
        
        # Track number of emails sent through this service instance
        self.emails_sent = 0
        
        # Track connection expiry - recreate client after 500 emails
        self.connection_email_limit = 500
        self.connection_timestamp = time.time()
    
    def _ensure_client(self, force_refresh=False):
        """
        Ensures the boto3 SES client is initialized when needed - implements lazy initialization.
        
        This method is the core of the lazy initialization pattern. It:
        1. Only creates the boto3 client when actually needed (when an email is about to be sent)
        2. Attempts to fetch credentials from the Flask application context first
        3. Falls back to environment variables if not in an application context
        4. Handles both production and development environments seamlessly
        
        This pattern prevents the common "RuntimeError: Working outside of application context"
        that occurs when Flask extensions are initialized at import time.
        """
        if self.client is None or force_refresh:
            try:
                # Always reload environment variables to get fresh values
                load_dotenv(find_dotenv(), override=True)
                
                # In Flask application context, get from app config
                self.aws_access_key_id = self.aws_access_key_id or current_app.config['AWS_ACCESS_KEY_ID']
                self.aws_secret_access_key = self.aws_secret_access_key or current_app.config['AWS_SECRET_ACCESS_KEY']
                self.region_name = self.region_name or current_app.config['AWS_REGION']
                
                # Always get sender email from environment or config
                self.sender_email = os.environ.get('SENDER_EMAIL') or current_app.config.get('SENDER_EMAIL')
                self.logger.info(f"Using sender email: {self.sender_email}")
                
                # Get configuration set for SES notifications
                self.configuration_set = os.environ.get('SES_CONFIGURATION_SET') or current_app.config.get('SES_CONFIGURATION_SET')
                if self.configuration_set:
                    self.logger.info(f"Using SES configuration set: {self.configuration_set}")
                else:
                    self.logger.warning("No SES configuration set found. Email status notifications won't be sent.")
            
            except RuntimeError:
                # Not in Flask app context and no credentials provided
                # Fallback to environment variables directly
                self.logger.warning("Not in Flask application context, using environment variables directly")
                self.aws_access_key_id = self.aws_access_key_id or os.environ.get('AWS_ACCESS_KEY_ID')
                self.aws_secret_access_key = self.aws_secret_access_key or os.environ.get('AWS_SECRET_ACCESS_KEY')
                self.region_name = self.region_name or os.environ.get('AWS_REGION')
                self.sender_email = os.environ.get('SENDER_EMAIL')
                self.configuration_set = os.environ.get('SES_CONFIGURATION_SET')
            
            # Now create the actual boto3 client with the gathered credentials
            self.client = boto3.client(
                'ses',
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.region_name,
                # Add connection timeouts and retries to prevent hanging
                config=boto3.session.Config(
                    connect_timeout=10,
                    read_timeout=10,
                    retries={'max_attempts': 3}
                )
            )
            self.logger.info("SES client created successfully")
            self.connection_timestamp = time.time()
            self.emails_sent = 0
    
    def send_email(self, recipient, subject, body_html, body_text=None, sender=None, sender_name=None, tracking_enabled=True, campaign_id=None, recipient_id=None, no_return_path=False):
        # Track email for AWS Free Tier usage monitoring
        try:
            from aws_usage import track_email_sent
            track_email_sent()
        except (ImportError, Exception) as e:
            self.logger.debug(f"AWS usage tracking not available: {str(e)}")
        """
        Send an email using Amazon SES
        
        Args:
            recipient: Email address of the recipient
            subject: Email subject
            body_html: HTML content for the email
            body_text: Plain text content for the email (optional)
            sender: Sender email address (optional, uses default if not provided)
            sender_name: Sender name (optional)
            tracking_enabled: Whether to enable open/click tracking (default: True)
            campaign_id: ID of the campaign this email belongs to (for tracking)
            recipient_id: ID of the recipient record (for tracking)
            no_return_path: If True, disable return path tracking to reduce SNS load (default: False)
        
        Returns:
            Message ID if successful, None otherwise
        """
        if not sender:
            sender = self.sender_email
        
        if sender_name:
            sender = f"{sender_name} <{sender}>"
        
        try:
            # Check if SNS notifications are globally disabled
            sns_disabled = os.environ.get('DISABLE_SNS_NOTIFICATIONS', 'false').lower() == 'true'
            if sns_disabled:
                self.logger.info(f"SNS notifications are disabled - skipping configuration set for {recipient}")
                # Don't use configuration set to prevent AWS from sending notifications
                use_config_set = False
            else:
                use_config_set = True
                
            # Apply tracking if enabled and we have the needed IDs
            if tracking_enabled and campaign_id and recipient_id and self.tracking_manager:
                # Process HTML to add tracking pixel and convert links
                body_html = self.tracking_manager.process_html_content(
                    body_html, campaign_id, recipient_id
                )
                self.logger.info(f"Added tracking to email for recipient {recipient}")
            
            # Prepare email message
            email_args = {
                'Source': sender,
                'Destination': {
                    'ToAddresses': [recipient]
                },
                'Message': {
                    'Subject': {
                        'Data': subject
                    },
                    'Body': {
                        'Html': {
                            'Data': body_html
                        }
                    }
                }
            }
            
            # Add plain text body if provided
            if body_text:
                email_args['Message']['Body']['Text'] = {'Data': body_text}
                
            # For headers, we need to add them as custom ReplyToAddresses
            # AWS SES v2 doesn't support custom headers directly in basic send_email
            # So we'll simplify to just make sure our emails work reliably
            if not no_return_path:
                # Only add bounce notification path for tracked emails
                email_args['ReturnPath'] = self.sender_email
                
            # Check if we need to refresh the client connection
            self.emails_sent += 1
            current_time = time.time()
            connection_age = current_time - self.connection_timestamp
            
            # Reset connection after either sending many emails or connection being old
            if self.emails_sent >= self.connection_email_limit or connection_age > 300:  # 5 minutes
                self.logger.info(f"Refreshing AWS SES connection after {self.emails_sent} emails or {connection_age:.1f} seconds")
                self.client = None
                self.connection_timestamp = current_time
                self.emails_sent = 0
            
            # Initialize SES client
            self._ensure_client()
            
            # Apply rate limiting to prevent API throttling
            if not self.rate_limiter.wait_for_token():
                self.logger.warning("Failed to acquire rate limit token after multiple retries")
                raise Exception("Rate limit exceeded - unable to send email after multiple retries")
            
            # First try with configuration set if it exists and SNS notifications aren't disabled
            if self.configuration_set and use_config_set:
                try:
                    # Add configuration set to a copy of email_args for the first attempt
                    first_attempt_args = email_args.copy()
                    first_attempt_args['ConfigurationSetName'] = self.configuration_set
                    self.logger.info(f"Using configuration set '{self.configuration_set}' for email to {recipient}")
                    
                    response = self.client.send_email(**first_attempt_args)
                    message_id = response['MessageId']
                    self.logger.info(f"Email sent to {recipient}, Message ID: {message_id}")
                    return message_id
                    
                except ClientError as e:
                    # If config set doesn't exist, try without it
                    if "ConfigurationSetDoesNotExist" in str(e):
                        self.logger.warning(f"Configuration set '{self.configuration_set}' does not exist in AWS SES. "
                                          f"Sending email without configuration set.")
                        # Set to None to avoid future errors
                        self.configuration_set = None
                    else:
                        # Re-raise if error is not related to configuration set
                        raise
            
            # Second attempt without configuration set
            response = self.client.send_email(**email_args)
            message_id = response['MessageId']
            self.logger.info(f"Email sent to {recipient} without configuration set, Message ID: {message_id}")
            return message_id
            
        except Exception as e:
            self.logger.error(f"Error sending email to {recipient}: {str(e)}", exc_info=True)
            return None

    def set_tracking_manager(self, tracking_manager):
        """Set the tracking manager for adding tracking to emails"""
        self.tracking_manager = tracking_manager
        self.logger.info("Tracking manager set for email service")
        
    def verify_email(self, email):
        """
        Verify an email address before sending
        
        Args:
            email: Email address to verify
            
        Returns:
            Tuple of (status, message) where status is 'valid', 'invalid', or 'risky'
        """
        from email_verification import EmailVerifier
        verifier = EmailVerifier()
        return verifier.verify_email(email)
        
    def batch_verify_emails(self, emails, max_workers=10):
        """
        Verify a batch of email addresses
        
        Args:
            emails: List of email addresses to verify
            max_workers: Maximum number of worker threads (default: 10)
            
        Returns:
            Dictionary with 'valid', 'invalid', and 'risky' keys containing lists of emails
        """
        from email_verification import EmailVerifier
        verifier = EmailVerifier()
        return verifier.batch_verify(emails, max_workers)
    
    def send_template_email(self, recipient, subject, template_html, template_text=None, 
                           template_data=None, sender=None, sender_name=None, 
                           tracking_enabled=False, campaign_id=None, recipient_id=None,
                           tags=None, no_return_path=True):
        """
        Send a templated email with optional personalization.
        
        Args:
            recipient: Email address of the recipient
            subject: Email subject
            template_html: HTML template to use (can include {{ variable }} placeholders)
            template_text: Plain text template (optional)
            template_data: Dictionary of values to use for template variables
            sender: Email address to use as sender (overrides the default)
            sender_name: Name to display as the sender
            tracking_enabled: Whether to enable tracking (legacy parameter)
            campaign_id: Campaign ID for tracking (legacy parameter)
            recipient_id: Recipient ID for tracking (legacy parameter)
            tags: List of tags to apply to the email
            no_return_path: If True, disable return path tracking to reduce SNS load (for large campaigns)
            
        Returns:
            message_id: The SES message ID if successful, None if failed
        """
        try:
            template_data = template_data or {}
            
            # Use default sender email if not provided
            if not sender:
                sender = self.sender_email
            
            # Add sender name if provided
            if sender_name:
                sender = f"{sender_name} <{sender}>"
            
            # Render template with provided data
            template = Template(template_html)
            body_html = template.safe_substitute(**template_data)
            
            body_text = None
            if template_text:
                text_template = Template(template_text)
                body_text = text_template.safe_substitute(**template_data)
            
            # Prepare email message
            email_args = {
                'Source': sender,
                'Destination': {
                    'ToAddresses': [recipient]
                },
                'Message': {
                    'Subject': {
                        'Data': subject
                    },
                    'Body': {
                        'Html': {
                            'Data': body_html
                        }
                    }
                }
            }
            
            # Add plain text body if provided
            if body_text:
                email_args['Message']['Body']['Text'] = {'Data': body_text}
                
            # For headers, we need to add them as custom ReplyToAddresses
            # AWS SES v2 doesn't support custom headers directly in basic send_email
            # So we'll simplify to just make sure our emails work reliably
            if not no_return_path:
                # Only add bounce notification path for tracked emails
                email_args['ReturnPath'] = self.sender_email
                
            # If no_return_path is enabled, disable the configuration set and return path
            # to prevent SES from sending notifications for large campaigns
            if no_return_path:
                self.logger.info(f"Return path tracking disabled for large campaign email to {recipient}")
                use_config_set = False  # Skip configuration set completely
            else:
                use_config_set = bool(self.configuration_set) and tracking_enabled  # Use it if it exists and tracking enabled
            
            # Check if we need to refresh the client connection
            self.emails_sent += 1
            current_time = time.time()
            connection_age = current_time - self.connection_timestamp
            
            # Reset connection after either sending many emails or connection being old
            if self.emails_sent >= self.connection_email_limit or connection_age > 300:  # 5 minutes
                self.logger.info(f"Refreshing AWS SES connection after {self.emails_sent} emails or {connection_age:.1f} seconds")
                self.client = None
                self.connection_timestamp = current_time
                self.emails_sent = 0
            
            # Initialize SES client
            self._ensure_client()
            
            # Apply rate limiting to prevent API throttling
            if not self.rate_limiter.wait_for_token():
                self.logger.warning("Failed to acquire rate limit token after multiple retries")
                raise Exception("Rate limit exceeded - unable to send email after multiple retries")
            
            # Only try with configuration set if it exists AND we should use it
            if use_config_set:
                try:
                    # Add configuration set to a copy of email_args for the first attempt
                    first_attempt_args = email_args.copy()
                    first_attempt_args['ConfigurationSetName'] = self.configuration_set
                    self.logger.info(f"Using configuration set '{self.configuration_set}' for email to {recipient}")
                    
                    response = self.client.send_email(**first_attempt_args)
                    message_id = response['MessageId']
                    self.logger.info(f"Email sent to {recipient}, Message ID: {message_id}")
                    return message_id
                    
                except ClientError as e:
                    # If config set doesn't exist, try without it
                    if "ConfigurationSetDoesNotExist" in str(e):
                        self.logger.warning(f"Configuration set '{self.configuration_set}' does not exist in AWS SES. "
                                          f"Sending email without configuration set.")
                        # Set to None to avoid future errors
                        self.configuration_set = None
                    else:
                        # Re-raise if error is not related to configuration set
                        raise
            
            # Second attempt without configuration set
            response = self.client.send_email(**email_args)
            message_id = response['MessageId']
            if no_return_path:
                self.logger.info(f"Email sent to {recipient} with tracking disabled, Message ID: {message_id}")
            else:
                self.logger.info(f"Email sent to {recipient} without configuration set, Message ID: {message_id}")
            return message_id
            
        except Exception as e:
            self.logger.error(f"Error sending email to {recipient}: {str(e)}", exc_info=True)
            return None
    
    def send_bulk_emails(self, recipients, subject, template_html, template_text=None, 
                        sender=None, sender_name=None, rate_limit=2, tracking_enabled=True, campaign_id=None):
        """
        Send bulk emails with rate limiting
        
        recipients: list of dicts with keys 'email', 'name', and custom data fields
        rate_limit: maximum emails per second
        """
        results = []
        sleep_time = 1.0 / rate_limit  # Time to wait between emails
        
        for recipient in recipients:
            email = recipient.pop('email')
            name = recipient.pop('name', None)
            
            # Customize the email with recipient data
            template_data = {'name': name}
            template_data.update(recipient)  # Add any other custom fields
            
            result = self.send_template_email(
                recipient=email,
                subject=subject,
                template_html=template_html,
                template_text=template_text,
                template_data=template_data,
                sender=sender,
                sender_name=sender_name,
                tracking_enabled=tracking_enabled,
                campaign_id=campaign_id,
                recipient_id=email
            )
            
            result['email'] = email
            results.append(result)
            
            # Rate limiting with additional pauses to prevent worker timeouts
            time.sleep(sleep_time)
            
            # More aggressive pausing strategy to prevent Render worker timeouts
            if len(results) % 20 == 0:
                self.logger.info(f"Added 3-second pause after sending {len(results)} emails to prevent server overload")
                time.sleep(3.0)
                
            # Extra long pause every 100 emails to completely reset worker timeout counter
            if len(results) % 100 == 0 and len(results) > 0:
                self.logger.info(f"Added 5-second extended pause after sending {len(results)} emails to reset worker timeout")
                time.sleep(5.0)
                
            # Ultra-defensive pause every 500 emails - this is right around where your timeouts happen
            if len(results) % 500 == 0 and len(results) > 0:
                self.logger.info(f"Added 10-second safety pause after sending {len(results)} emails")
                time.sleep(10.0)
            
        return results
