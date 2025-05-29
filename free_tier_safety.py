"""
AWS Free Tier Safety System

This module implements safety features to prevent exceeding AWS Free Tier limits by:
1. Checking current AWS usage before processing campaigns
2. Warning users when approaching limits (85%)
3. Optionally pausing campaigns when limits are exceeded

Works with the existing token bucket rate limiter for optimal AWS resource usage.
"""

import logging
from aws_usage_model import AWSUsageStats
import os
from datetime import datetime
from functools import wraps

# Configure logging
logger = logging.getLogger(__name__)

# Free tier limits
SES_MONTHLY_LIMIT = 3000  # 3,000 emails per month
SNS_MONTHLY_LIMIT = 100000  # 100,000 notifications per month

# Warning thresholds
WARNING_THRESHOLD = 0.85  # 85% of limit
CRITICAL_THRESHOLD = 0.95  # 95% of limit

# Environment variable to control campaign pausing
AUTO_PAUSE_CAMPAIGNS = os.environ.get('AUTO_PAUSE_CAMPAIGNS', 'TRUE').upper() == 'TRUE'

class FreeTierLimitExceeded(Exception):
    """Exception raised when AWS Free Tier limits would be exceeded by an operation"""
    pass

class FreeTierWarning(Exception):
    """Warning raised when AWS Free Tier limits are approaching the threshold"""
    pass

def check_free_tier_limits(campaign=None, recipient_count=0):
    """
    Check if the current AWS usage is approaching or exceeding Free Tier limits
    
    Args:
        campaign: The EmailCampaign object (optional)
        recipient_count: Number of recipients in the campaign (optional)
        
    Returns:
        dict: Status information with usage details
        
    Raises:
        FreeTierWarning: When usage is approaching the warning threshold
        FreeTierLimitExceeded: When usage would exceed the free tier limit
    """
    try:
        # Get current monthly usage
        usage = AWSUsageStats.get_monthly_usage()
        
        # Calculate projected usage if this campaign is sent
        projected_email_usage = usage['email_total'] + recipient_count
        projected_email_percent = min(100, round((projected_email_usage / SES_MONTHLY_LIMIT) * 100, 1))
        
        # Estimated SNS notifications based on email count (approximate)
        # Most emails generate ~3 notifications (send, delivery, open/click)
        estimated_sns = recipient_count * 3
        projected_sns_usage = usage['sns_total'] + estimated_sns
        projected_sns_percent = min(100, round((projected_sns_usage / SNS_MONTHLY_LIMIT) * 100, 1))
        
        # Prepare status information
        status = {
            'current_usage': {
                'email': {
                    'count': usage['email_total'],
                    'percent': usage['email_percent'],
                    'limit': SES_MONTHLY_LIMIT
                },
                'sns': {
                    'count': usage['sns_total'],
                    'percent': usage['sns_percent'],
                    'limit': SNS_MONTHLY_LIMIT
                }
            },
            'projected_usage': {
                'email': {
                    'count': projected_email_usage,
                    'percent': projected_email_percent,
                    'limit': SES_MONTHLY_LIMIT
                },
                'sns': {
                    'count': projected_sns_usage,
                    'percent': projected_sns_percent,
                    'limit': SNS_MONTHLY_LIMIT
                }
            },
            'campaign_info': {
                'recipient_count': recipient_count,
                'name': campaign.name if campaign else None,
                'id': campaign.id if campaign else None
            },
            'auto_pause_enabled': AUTO_PAUSE_CAMPAIGNS,
            'threshold': {
                'warning': WARNING_THRESHOLD * 100,
                'critical': CRITICAL_THRESHOLD * 100
            }
        }
        
        # Check if projected usage exceeds free tier critical threshold
        if (projected_email_percent/100 > CRITICAL_THRESHOLD or 
            projected_sns_percent/100 > CRITICAL_THRESHOLD):
            
            error_message = (
                f"⚠️ CRITICAL: AWS Free Tier limits would be exceeded by this campaign!\n"
                f"Email usage: {projected_email_usage}/{SES_MONTHLY_LIMIT} ({projected_email_percent}%)\n"
                f"SNS usage: {projected_sns_usage}/{SNS_MONTHLY_LIMIT} ({projected_sns_percent}%)"
            )
            
            if AUTO_PAUSE_CAMPAIGNS:
                error_message += "\nCampaign has been automatically paused to prevent AWS billing charges."
                
            logger.critical(error_message)
            status['status'] = 'critical'
            status['message'] = error_message
            
            raise FreeTierLimitExceeded(error_message)
            
        # Check if projected usage exceeds warning threshold
        elif (projected_email_percent/100 > WARNING_THRESHOLD or 
              projected_sns_percent/100 > WARNING_THRESHOLD):
            
            warning_message = (
                f"⚠️ WARNING: This campaign will approach AWS Free Tier limits!\n"
                f"Email usage: {projected_email_usage}/{SES_MONTHLY_LIMIT} ({projected_email_percent}%)\n"
                f"SNS usage: {projected_sns_usage}/{SNS_MONTHLY_LIMIT} ({projected_sns_percent}%)"
            )
            
            logger.warning(warning_message)
            status['status'] = 'warning'
            status['message'] = warning_message
            
            raise FreeTierWarning(warning_message)
            
        # Usage is within acceptable limits
        else:
            status['status'] = 'ok'
            status['message'] = "AWS Free Tier usage is within acceptable limits"
            return status
            
    except (FreeTierWarning, FreeTierLimitExceeded):
        # Re-raise these specific exceptions
        raise
    except Exception as e:
        # Log other errors but don't block the campaign
        logger.error(f"Error checking AWS Free Tier limits: {str(e)}")
        return {
            'status': 'error',
            'message': f"Error checking AWS Free Tier limits: {str(e)}"
        }

def pause_campaign_if_limit_exceeded(campaign):
    """
    Pause a campaign if it would exceed AWS Free Tier limits
    
    Args:
        campaign: The EmailCampaign object to check and potentially pause
        
    Returns:
        bool: True if campaign is safe to run, False if paused
    """
    from models import db, EmailCampaign
    
    if not campaign:
        return True
        
    try:
        # Get the recipient count
        recipient_count = campaign.recipients.count()
        
        # Check if campaign would exceed limits
        check_free_tier_limits(campaign, recipient_count)
        
        # If we got here, the campaign is safe to run
        return True
    
    except FreeTierLimitExceeded:
        # Pause the campaign if auto-pause is enabled
        if AUTO_PAUSE_CAMPAIGNS:
            try:
                campaign.status = 'paused'
                campaign.updated_at = datetime.utcnow()
                db.session.commit()
                logger.warning(f"Campaign {campaign.id} ({campaign.name}) has been paused due to AWS Free Tier limits")
                return False
            except Exception as e:
                logger.error(f"Error pausing campaign {campaign.id}: {str(e)}")
                
        return False
    
    except FreeTierWarning:
        # Campaign can still run, but a warning has been logged
        return True
    
    except Exception as e:
        # Log error but allow campaign to run
        logger.error(f"Error in pause_campaign_if_limit_exceeded: {str(e)}")
        return True

def free_tier_safety_check(func):
    """
    Decorator to check AWS Free Tier limits before sending emails
    
    This can be applied to email sending functions to automatically check
    if the operation would exceed AWS Free Tier limits.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Try to find a campaign object in the arguments
        campaign = None
        recipient_count = 0
        
        # Look for a campaign object in args and kwargs
        for arg in args:
            if hasattr(arg, '__class__') and arg.__class__.__name__ == 'EmailCampaign':
                campaign = arg
                break
                
        if 'campaign' in kwargs:
            campaign = kwargs['campaign']
            
        # If we found a campaign, check if it would exceed limits
        if campaign:
            recipient_count = campaign.recipients.count()
            
            try:
                check_free_tier_limits(campaign, recipient_count)
            except FreeTierLimitExceeded:
                if AUTO_PAUSE_CAMPAIGNS:
                    # Pause the campaign and abort the function
                    pause_campaign_if_limit_exceeded(campaign)
                    return None
            except FreeTierWarning:
                # Warning already logged, continue with function
                pass
                
        # Execute the original function
        return func(*args, **kwargs)
        
    return wrapper
