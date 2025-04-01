"""
AWS Usage Dashboard and API Routes

This module adds AWS usage monitoring features to track:
1. Total emails sent (SES)
2. Total SNS notifications received
3. Total SQS messages processed

This helps you monitor your AWS Free Tier usage limits.
"""

from flask import Blueprint, render_template, jsonify, request
from aws_usage_model import AWSUsageStats
import logging
import os
import datetime

# Import CloudWatch metrics (with fallback if not available)
try:
    from aws_cloudwatch_metrics import get_cloudwatch_metrics
    cloudwatch_available = True
except ImportError:
    cloudwatch_available = False

# Configure logging
logger = logging.getLogger(__name__)

# Create Blueprint for AWS usage features
aws_usage_blueprint = Blueprint('aws_usage', __name__)

@aws_usage_blueprint.route('/aws-usage', methods=['GET'])
def aws_usage_dashboard():
    """
    Display the AWS usage dashboard to monitor free tier limits
    """
    return render_template('aws_usage_dashboard.html')

# Control whether to use CloudWatch or local tracking (default to True if available)
USE_CLOUDWATCH = os.environ.get('USE_CLOUDWATCH', 'TRUE').upper() == 'TRUE' and cloudwatch_available

@aws_usage_blueprint.route('/api/aws-usage', methods=['GET'])
def get_aws_usage():
    """Get current AWS usage statistics for the dashboard"""
    try:
        # Add cache-busting headers to ensure fresh data
        response_headers = {
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
        }
        
        # Check if using real-time CloudWatch data was explicitly requested
        use_cloudwatch = request.args.get('use_cloudwatch', 'false').lower() == 'true'
        
        # Check if cache should be bypassed (used by the refresh button)
        bypass_cache = request.args.get('bypass_cache', 'false').lower() == 'true'
        
        # Only use CloudWatch if enabled globally AND specifically requested in this request
        # This prevents automatic background requests from making CloudWatch API calls
        if USE_CLOUDWATCH and use_cloudwatch and cloudwatch_available:
            # Get real usage data from CloudWatch (only when explicitly requested)
            logger.info("Fetching real-time AWS usage data from CloudWatch")
            
            try:
                # Get CloudWatch metrics (with caching to minimize API calls)
                cloudwatch = get_cloudwatch_metrics()
                aws_metrics = cloudwatch.get_aws_free_tier_metrics()
                
                # Create response with real CloudWatch data
                response = {
                    'monthly': {
                        'email_total': aws_metrics['ses']['sent'],
                        'email_limit': 3000,
                        'email_percent': aws_metrics['ses']['free_tier_percent'],
                        'sns_total': aws_metrics['sns']['published'],
                        'sns_limit': 100000,
                        'sns_percent': aws_metrics['sns']['free_tier_percent'],
                        'sqs_total': aws_metrics['sqs']['received']
                    },
                    'today': {
                        'emails_sent': aws_metrics['ses']['sent'],
                        'emails_delivered': aws_metrics['ses']['delivered'],
                        'emails_bounced': aws_metrics['ses']['bounced'],
                        'emails_complained': aws_metrics['ses']['complained'],
                        'sns_notifications': aws_metrics['sns']['published'],
                        'sqs_messages': aws_metrics['sqs']['received']
                    },
                    'source': 'cloudwatch',
                    'last_updated': aws_metrics['timestamp']
                }
                
                # After getting CloudWatch data, update local tracking for accuracy
                update_local_tracking_from_cloudwatch(aws_metrics)
                
                return jsonify(response), 200, response_headers
            except Exception as e:
                logger.error(f"Error fetching CloudWatch metrics: {str(e)}")
                # Fall back to local tracking if CloudWatch fails
                pass
        
        # Use local tracking data from database
        # Always force a fresh database read to get real-time data
        # This is crucial for working with the token bucket rate limiter
        logger.info("Performing direct database query for latest AWS usage stats")
        from models import db
        
        # Commit any pending transactions and clear query cache
        try:
            db.session.commit()
        except:
            db.session.rollback()
        
        # Clear SQLAlchemy query cache to ensure fresh data
        db.session.expire_all()
        
        # Create direct SQL query instead of using the model method
        # This completely bypasses any caching layers
        current_month = datetime.datetime.utcnow().month
        current_year = datetime.datetime.utcnow().year
        
        # Get current monthly usage stats with direct SQL for guaranteed fresh data
        logger.info(f"Fetching real-time monthly usage data for {current_month}/{current_year}")
        
        if bypass_cache:
            # Perform a completely fresh calculation directly from the database
            logger.info("Performing complete recalculation of monthly statistics")
            usage = AWSUsageStats.get_monthly_usage(force_recalculate=True)
        else:
            # Use regular method but after clearing cache
            usage = AWSUsageStats.get_monthly_usage()
        
        # Add today's stats
        logger.info("Fetching today's stats from local database")
        today_stats = AWSUsageStats.get_or_create_today()
        
        # Debug logging
        logger.info(f"Today's stats: Emails = {today_stats.emails_sent_count}, SNS = {today_stats.sns_notifications_count}")
        logger.info(f"Monthly stats: Emails = {usage['email_total']}, SNS = {usage['sns_total']}")
        
        response = {
            'monthly': {
                'email_total': usage['email_total'],
                'email_limit': 3000,
                'email_percent': usage['email_percent'],
                'sns_total': usage['sns_total'],
                'sns_limit': 100000,
                'sns_percent': usage['sns_percent'],
                'sqs_total': usage['sqs_total']
            },
            'today': {
                'emails_sent': today_stats.emails_sent_count,
                'emails_delivered': today_stats.emails_delivered_count,
                'emails_bounced': today_stats.emails_bounced_count,
                'emails_complained': today_stats.emails_complained_count,
                'sns_notifications': today_stats.sns_notifications_count,
                'sqs_messages': today_stats.sqs_messages_processed_count
            },
            'source': 'local_tracking'
        }
        
        return jsonify(response), 200, response_headers
    except Exception as e:
        logger.error(f"Error getting AWS usage stats: {str(e)}")
        return jsonify({
            'error': str(e)
        }), 500, response_headers

@aws_usage_blueprint.route('/aws-optimizer', methods=['GET'])
def aws_optimizer():
    """Run the AWS usage optimizer to stay within free tier limits"""
    try:
        # Import the optimizer
        from aws_usage_optimizer import main as run_optimizer
        
        # Run the optimizer
        run_optimizer()
        
        # Return to the dashboard with success message
        return render_template('aws_usage_dashboard.html', 
                              message="AWS usage optimization completed successfully!")
    except Exception as e:
        logger.error(f"Error running AWS usage optimizer: {str(e)}")
        return render_template('aws_usage_dashboard.html', 
                              error=f"Error optimizing AWS usage: {str(e)}")

# Helper functions for tracking usage
def track_email_sent():
    """Track an email send for AWS usage monitoring"""
    try:
        AWSUsageStats.increment_email_sent()
    except Exception as e:
        logger.error(f"Error tracking email sent: {str(e)}")

def track_sns_notification():
    """Track an SNS notification for AWS usage monitoring"""
    try:
        AWSUsageStats.increment_sns_notification()
    except Exception as e:
        logger.error(f"Error tracking SNS notification: {str(e)}")

def track_sqs_message():
    """Track a SQS message for AWS usage monitoring"""
    try:
        AWSUsageStats.increment_sqs_message_processed()
    except Exception as e:
        logger.error(f"Error tracking SQS message: {str(e)}")
        
def update_local_tracking_from_cloudwatch(aws_metrics):
    """Update local tracking database with data from CloudWatch
    
    This ensures our local tracking stays in sync with actual AWS usage,
    which is especially important for the free tier safety feature.
    """
    try:
        # Get today's stats record
        today_stats = AWSUsageStats.get_or_create_today()
        
        # Only update if the CloudWatch values are higher than our local tracking
        # This prevents overwriting our tracking with incomplete CloudWatch data
        if aws_metrics['ses']['sent'] > today_stats.emails_sent_count:
            today_stats.emails_sent_count = aws_metrics['ses']['sent']
            
        if aws_metrics['ses']['delivered'] > today_stats.emails_delivered_count:
            today_stats.emails_delivered_count = aws_metrics['ses']['delivered']
            
        if aws_metrics['ses']['bounced'] > today_stats.emails_bounced_count:
            today_stats.emails_bounced_count = aws_metrics['ses']['bounced']
            
        if aws_metrics['ses']['complained'] > today_stats.emails_complained_count:
            today_stats.emails_complained_count = aws_metrics['ses']['complained']
            
        if aws_metrics['sns']['published'] > today_stats.sns_notifications_count:
            today_stats.sns_notifications_count = aws_metrics['sns']['published']
            
        if aws_metrics['sqs']['received'] > today_stats.sqs_messages_processed_count:
            today_stats.sqs_messages_processed_count = aws_metrics['sqs']['received']
            
        # Save the updates
        from models import db
        db.session.commit()
        
        logger.info("Updated local tracking with CloudWatch data")
    except Exception as e:
        logger.error(f"Error updating local tracking from CloudWatch: {str(e)}")
