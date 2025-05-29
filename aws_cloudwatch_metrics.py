"""
AWS CloudWatch Metrics Integration

This module fetches real AWS usage data from CloudWatch for:
- SES email sends
- SNS notifications
- SQS messages processed

It caches results to minimize API calls and costs, only updating when explicitly requested.
"""

import os
import boto3
import logging
import datetime
from functools import lru_cache
from datetime import datetime, timedelta

# Configure logging
logger = logging.getLogger(__name__)

class CloudWatchMetrics:
    """
    Fetches and caches AWS usage data from CloudWatch.
    
    This implementation is carefully designed to minimize API calls by:
    1. Using lru_cache to prevent duplicate requests
    2. Only fetching metrics when explicitly requested
    3. Supporting a refresh-only approach to prevent background polling
    
    This approach aligns with Render's free tier constraints and works with
    the application's existing token bucket rate limiter.
    """
    
    def __init__(self, region_name=None):
        """Initialize the CloudWatch metrics client"""
        self.region_name = region_name or os.environ.get('AWS_REGION', 'us-east-1')
        
        # AWS credentials
        self.aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
        self.aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
        
        # Create boto3 clients
        self._cloudwatch = None
        self._ses_client = None
        self._sns_client = None
        self._sqs_client = None
        
        # Cache timeouts
        self.cache_timeout = 300  # 5 minutes in seconds
        
        # Initialize clients
        self._init_clients()
    
    def _init_clients(self):
        """Initialize AWS clients only when needed"""
        try:
            # Only create the client if we have credentials
            if self.aws_access_key_id and self.aws_secret_access_key:
                self._cloudwatch = boto3.client(
                    'cloudwatch',
                    region_name=self.region_name,
                    aws_access_key_id=self.aws_access_key_id,
                    aws_secret_access_key=self.aws_secret_access_key
                )
                
                # Create service-specific clients for account limits
                self._ses_client = boto3.client(
                    'sesv2', 
                    region_name=self.region_name,
                    aws_access_key_id=self.aws_access_key_id,
                    aws_secret_access_key=self.aws_secret_access_key
                )
                
                self._sns_client = boto3.client(
                    'sns', 
                    region_name=self.region_name,
                    aws_access_key_id=self.aws_access_key_id,
                    aws_secret_access_key=self.aws_secret_access_key
                )
                
                self._sqs_client = boto3.client(
                    'sqs', 
                    region_name=self.region_name, 
                    aws_access_key_id=self.aws_access_key_id,
                    aws_secret_access_key=self.aws_secret_access_key
                )
                
                logger.info("AWS CloudWatch client initialized successfully")
            else:
                logger.warning("AWS credentials not found. CloudWatch metrics will not be available.")
        except Exception as e:
            logger.error(f"Error initializing CloudWatch client: {str(e)}")
    
    @lru_cache(maxsize=10)
    def get_metric_statistics(self, namespace, metric_name, dimensions, start_time, end_time, period=3600, statistics=['Sum']):
        """
        Get metric statistics from CloudWatch with caching to minimize API calls
        
        Args:
            namespace: The CloudWatch namespace (e.g., 'AWS/SES')
            metric_name: The name of the metric (e.g., 'Send')
            dimensions: List of dimensions to filter by
            start_time: Start time for metrics query
            end_time: End time for metrics query
            period: Period in seconds (default: 1 hour)
            statistics: List of statistics to retrieve (default: ['Sum'])
            
        Returns:
            The metric statistics or None if the client is not initialized
        """
        if not self._cloudwatch:
            logger.warning("CloudWatch client not initialized. Cannot fetch metrics.")
            return None
            
        try:
            response = self._cloudwatch.get_metric_statistics(
                Namespace=namespace,
                MetricName=metric_name,
                Dimensions=dimensions,
                StartTime=start_time,
                EndTime=end_time,
                Period=period,
                Statistics=statistics
            )
            
            return response
        except Exception as e:
            logger.error(f"Error fetching CloudWatch metric {namespace}/{metric_name}: {str(e)}")
            return None
    
    def get_ses_send_statistics(self, days=30):
        """
        Get SES send statistics for the specified number of days
        
        Args:
            days: Number of days to look back (default: 30)
            
        Returns:
            Dictionary with SES send statistics or default values if not available
        """
        if not self._cloudwatch:
            logger.warning("CloudWatch client not initialized. Cannot fetch SES statistics.")
            return {
                'sent': 0,
                'delivered': 0,
                'bounced': 0,
                'complained': 0,
                'rejected': 0
            }
            
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        
        # Define dimensions (empty for account-level metrics)
        dimensions = []
        
        # Fetch send metrics
        sent_response = self.get_metric_statistics(
            namespace='AWS/SES',
            metric_name='Send',
            dimensions=dimensions,
            start_time=start_time,
            end_time=end_time,
            period=days * 24 * 3600,  # One data point for the entire period
            statistics=['Sum']
        )
        
        # Fetch delivery metrics
        delivered_response = self.get_metric_statistics(
            namespace='AWS/SES',
            metric_name='Delivery',
            dimensions=dimensions,
            start_time=start_time,
            end_time=end_time,
            period=days * 24 * 3600,
            statistics=['Sum']
        )
        
        # Fetch bounce metrics
        bounce_response = self.get_metric_statistics(
            namespace='AWS/SES',
            metric_name='Bounce',
            dimensions=dimensions,
            start_time=start_time,
            end_time=end_time,
            period=days * 24 * 3600,
            statistics=['Sum']
        )
        
        # Fetch complaint metrics
        complaint_response = self.get_metric_statistics(
            namespace='AWS/SES',
            metric_name='Complaint',
            dimensions=dimensions,
            start_time=start_time,
            end_time=end_time,
            period=days * 24 * 3600,
            statistics=['Sum']
        )
        
        # Fetch rejection metrics
        reject_response = self.get_metric_statistics(
            namespace='AWS/SES',
            metric_name='Reject',
            dimensions=dimensions,
            start_time=start_time,
            end_time=end_time,
            period=days * 24 * 3600,
            statistics=['Sum']
        )
        
        # Extract values or default to 0
        sent = 0
        if sent_response and 'Datapoints' in sent_response and sent_response['Datapoints']:
            sent = int(sent_response['Datapoints'][0].get('Sum', 0))
            
        delivered = 0
        if delivered_response and 'Datapoints' in delivered_response and delivered_response['Datapoints']:
            delivered = int(delivered_response['Datapoints'][0].get('Sum', 0))
            
        bounced = 0
        if bounce_response and 'Datapoints' in bounce_response and bounce_response['Datapoints']:
            bounced = int(bounce_response['Datapoints'][0].get('Sum', 0))
            
        complained = 0
        if complaint_response and 'Datapoints' in complaint_response and complaint_response['Datapoints']:
            complained = int(complaint_response['Datapoints'][0].get('Sum', 0))
            
        rejected = 0
        if reject_response and 'Datapoints' in reject_response and reject_response['Datapoints']:
            rejected = int(reject_response['Datapoints'][0].get('Sum', 0))
        
        return {
            'sent': sent,
            'delivered': delivered,
            'bounced': bounced,
            'complained': complained,
            'rejected': rejected
        }
    
    def get_sns_statistics(self, days=30):
        """
        Get SNS publish statistics for the specified number of days
        
        Args:
            days: Number of days to look back (default: 30)
            
        Returns:
            Dictionary with SNS publish statistics or default values if not available
        """
        if not self._cloudwatch:
            logger.warning("CloudWatch client not initialized. Cannot fetch SNS statistics.")
            return {
                'published': 0,
                'delivered': 0,
                'failed': 0
            }
            
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        
        # Define dimensions (empty for account-level metrics)
        dimensions = []
        
        # Fetch publish metrics
        publish_response = self.get_metric_statistics(
            namespace='AWS/SNS',
            metric_name='NumberOfMessagesPublished',
            dimensions=dimensions,
            start_time=start_time,
            end_time=end_time,
            period=days * 24 * 3600,  # One data point for the entire period
            statistics=['Sum']
        )
        
        # Fetch delivery metrics
        delivered_response = self.get_metric_statistics(
            namespace='AWS/SNS',
            metric_name='NumberOfNotificationsDelivered',
            dimensions=dimensions,
            start_time=start_time,
            end_time=end_time,
            period=days * 24 * 3600,
            statistics=['Sum']
        )
        
        # Fetch failed metrics
        failed_response = self.get_metric_statistics(
            namespace='AWS/SNS',
            metric_name='NumberOfNotificationsFailed',
            dimensions=dimensions,
            start_time=start_time,
            end_time=end_time,
            period=days * 24 * 3600,
            statistics=['Sum']
        )
        
        # Extract values or default to 0
        published = 0
        if publish_response and 'Datapoints' in publish_response and publish_response['Datapoints']:
            published = int(publish_response['Datapoints'][0].get('Sum', 0))
            
        delivered = 0
        if delivered_response and 'Datapoints' in delivered_response and delivered_response['Datapoints']:
            delivered = int(delivered_response['Datapoints'][0].get('Sum', 0))
            
        failed = 0
        if failed_response and 'Datapoints' in failed_response and failed_response['Datapoints']:
            failed = int(failed_response['Datapoints'][0].get('Sum', 0))
        
        return {
            'published': published,
            'delivered': delivered,
            'failed': failed
        }
    
    def get_sqs_statistics(self, days=30):
        """
        Get SQS message statistics for the specified number of days
        
        Args:
            days: Number of days to look back (default: 30)
            
        Returns:
            Dictionary with SQS message statistics or default values if not available
        """
        if not self._cloudwatch:
            logger.warning("CloudWatch client not initialized. Cannot fetch SQS statistics.")
            return {
                'received': 0,
                'deleted': 0
            }
            
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        
        # Get SQS queue URL from environment
        queue_name = os.environ.get('SQS_QUEUE_NAME', 'email-bulk-notifications')
        
        # Try to get queue URL
        queue_url = None
        try:
            if self._sqs_client:
                response = self._sqs_client.get_queue_url(QueueName=queue_name)
                queue_url = response.get('QueueUrl')
                
                # Extract queue name from URL
                queue_name = queue_url.split('/')[-1]
        except Exception as e:
            logger.error(f"Error getting SQS queue URL: {str(e)}")
        
        # Define dimensions for the specific queue
        dimensions = []
        if queue_name:
            dimensions = [{'Name': 'QueueName', 'Value': queue_name}]
        
        # Fetch received message metrics
        received_response = self.get_metric_statistics(
            namespace='AWS/SQS',
            metric_name='NumberOfMessagesReceived',
            dimensions=dimensions,
            start_time=start_time,
            end_time=end_time,
            period=days * 24 * 3600,  # One data point for the entire period
            statistics=['Sum']
        )
        
        # Fetch deleted message metrics
        deleted_response = self.get_metric_statistics(
            namespace='AWS/SQS',
            metric_name='NumberOfMessagesDeleted',
            dimensions=dimensions,
            start_time=start_time,
            end_time=end_time,
            period=days * 24 * 3600,
            statistics=['Sum']
        )
        
        # Extract values or default to 0
        received = 0
        if received_response and 'Datapoints' in received_response and received_response['Datapoints']:
            received = int(received_response['Datapoints'][0].get('Sum', 0))
            
        deleted = 0
        if deleted_response and 'Datapoints' in deleted_response and deleted_response['Datapoints']:
            deleted = int(deleted_response['Datapoints'][0].get('Sum', 0))
        
        return {
            'received': received,
            'deleted': deleted
        }
    
    def get_ses_sending_quota(self):
        """
        Get SES sending quota information
        
        Returns:
            Dictionary with SES quota information or default values if not available
        """
        if not self._ses_client:
            logger.warning("SES client not initialized. Cannot fetch sending quota.")
            return {
                'max_send_rate': 14,  # Default for SES
                'max_24_hour_send': 200,  # Default starting limit
                'sent_last_24_hours': 0,
                'sending_enabled': True
            }
            
        try:
            response = self._ses_client.get_account()
            
            if 'SendQuota' in response:
                quota = response['SendQuota']
                return {
                    'max_send_rate': quota.get('MaxSendRate', 14),
                    'max_24_hour_send': quota.get('Max24HourSend', 200),
                    'sent_last_24_hours': quota.get('SentLast24Hours', 0),
                    'sending_enabled': response.get('SendingEnabled', True)
                }
            else:
                logger.warning("SES sending quota information not available in response")
                return {
                    'max_send_rate': 14,
                    'max_24_hour_send': 200,
                    'sent_last_24_hours': 0,
                    'sending_enabled': True
                }
        except Exception as e:
            logger.error(f"Error fetching SES sending quota: {str(e)}")
            return {
                'max_send_rate': 14,
                'max_24_hour_send': 200,
                'sent_last_24_hours': 0,
                'sending_enabled': True
            }
    
    def get_aws_free_tier_metrics(self):
        """
        Get comprehensive AWS free tier usage metrics
        
        Returns:
            Dictionary with all relevant AWS usage metrics for free tier monitoring
        """
        # Get SES statistics
        ses_stats = self.get_ses_send_statistics()
        
        # Get SNS statistics
        sns_stats = self.get_sns_statistics()
        
        # Get SQS statistics
        sqs_stats = self.get_sqs_statistics()
        
        # Get SES quota information
        ses_quota = self.get_ses_sending_quota()
        
        # Free tier limits
        free_tier_limits = {
            'ses_monthly': 3000,  # 3,000 emails per month
            'sns_monthly': 100000,  # 100,000 notifications per month
            'sqs_monthly': 1000000  # 1 million requests per month
        }
        
        # Calculate percentages
        try:
            ses_percent = min(100, round((ses_stats['sent'] / free_tier_limits['ses_monthly']) * 100, 1))
        except:
            ses_percent = 0
            
        try:
            sns_percent = min(100, round((sns_stats['published'] / free_tier_limits['sns_monthly']) * 100, 1))
        except:
            sns_percent = 0
            
        try:
            sqs_percent = min(100, round((sqs_stats['received'] / free_tier_limits['sqs_monthly']) * 100, 1))
        except:
            sqs_percent = 0
        
        # Compile all metrics into a single response
        return {
            'ses': {
                'sent': ses_stats['sent'],
                'delivered': ses_stats['delivered'],
                'bounced': ses_stats['bounced'],
                'complained': ses_stats['complained'],
                'rejected': ses_stats['rejected'],
                'quota': {
                    'max_send_rate': ses_quota['max_send_rate'],
                    'max_24_hour_send': ses_quota['max_24_hour_send'],
                    'sent_last_24_hours': ses_quota['sent_last_24_hours'],
                    'sending_enabled': ses_quota['sending_enabled']
                },
                'free_tier_limit': free_tier_limits['ses_monthly'],
                'free_tier_percent': ses_percent
            },
            'sns': {
                'published': sns_stats['published'],
                'delivered': sns_stats['delivered'],
                'failed': sns_stats['failed'],
                'free_tier_limit': free_tier_limits['sns_monthly'],
                'free_tier_percent': sns_percent
            },
            'sqs': {
                'received': sqs_stats['received'],
                'deleted': sqs_stats['deleted'],
                'free_tier_limit': free_tier_limits['sqs_monthly'],
                'free_tier_percent': sqs_percent
            },
            'timestamp': datetime.utcnow().isoformat()
        }

# Singleton instance
_cloudwatch_metrics = None

def get_cloudwatch_metrics():
    """Get the singleton CloudWatchMetrics instance"""
    global _cloudwatch_metrics
    if _cloudwatch_metrics is None:
        _cloudwatch_metrics = CloudWatchMetrics()
    return _cloudwatch_metrics
