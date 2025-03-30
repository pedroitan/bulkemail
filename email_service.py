"""
Email Service Module

This module provides email sending functionality using Amazon SES with a lazy initialization pattern.
The SESEmailService implements a pattern that only initializes the boto3 client when needed,
preventing issues when working outside the Flask application context.
"""

import boto3
from botocore.exceptions import ClientError
import logging
import time
from flask import current_app
from string import Template
import os
from dotenv import load_dotenv, find_dotenv

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
    
    def _ensure_client(self):
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
        if self.client is None:
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
                region_name=self.region_name
            )
            self.logger.info("SES client created successfully")
    
    def send_email(self, recipient, subject, body_html, body_text=None, sender=None, sender_name=None, tracking_enabled=True, campaign_id=None, recipient_id=None):
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
        
        Returns:
            Message ID if successful, None otherwise
        """
        if not sender:
            sender = self.sender_email
        
        if sender_name:
            sender = f"{sender_name} <{sender}>"
        
        try:
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
            
            # Initialize SES client
            self._ensure_client()
            
            # First try with configuration set if it exists
            if self.configuration_set:
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
                           template_data=None, sender=None, sender_name=None, tracking_enabled=True, campaign_id=None, recipient_id=None):
        """
        Send email with template variables replaced
        """
        template_data = template_data or {}
        
        # Replace template variables
        html_template = Template(template_html)
        html_content = html_template.safe_substitute(template_data)
        
        text_content = None
        if template_text:
            text_template = Template(template_text)
            text_content = text_template.safe_substitute(template_data)
        
        return self.send_email(
            recipient=recipient,
            subject=subject,
            body_html=html_content,
            body_text=text_content,
            sender=sender,
            sender_name=sender_name,
            tracking_enabled=tracking_enabled,
            campaign_id=campaign_id,
            recipient_id=recipient_id
        )
    
    def send_bulk_emails(self, recipients, subject, template_html, template_text=None, 
                        sender=None, sender_name=None, rate_limit=10, tracking_enabled=True, campaign_id=None):
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
            
            # Rate limiting
            time.sleep(sleep_time)
            
        return results
