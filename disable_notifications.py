"""
Notification Disabler

This module provides a simple way to globally disable all SNS notifications
and SQS processing while preserving email sending functionality.
"""

import os
from dotenv import load_dotenv, set_key, find_dotenv

# Load environment variables
load_dotenv()
env_file = find_dotenv()

def disable_all_notifications():
    """
    Disable all SNS notifications and SQS processing by setting environment variables.
    This will preserve email sending functionality while preventing notification overload.
    """
    # Set environment variables
    os.environ['DISABLE_SNS_NOTIFICATIONS'] = 'true'
    os.environ['DISABLE_SQS_PROCESSING'] = 'true'
    
    # Save to .env file for persistence
    set_key(env_file, 'DISABLE_SNS_NOTIFICATIONS', 'true')
    set_key(env_file, 'DISABLE_SQS_PROCESSING', 'true')
    
    print("✅ All SNS notifications and SQS processing have been disabled.")
    print("Email sending will still work, but no delivery tracking will be available.")

def enable_all_notifications():
    """
    Re-enable all SNS notifications and SQS processing.
    """
    # Set environment variables
    os.environ['DISABLE_SNS_NOTIFICATIONS'] = 'false'
    os.environ['DISABLE_SQS_PROCESSING'] = 'false'
    
    # Save to .env file for persistence
    set_key(env_file, 'DISABLE_SNS_NOTIFICATIONS', 'false')
    set_key(env_file, 'DISABLE_SQS_PROCESSING', 'false')
    
    print("✅ All SNS notifications and SQS processing have been re-enabled.")
    print("Full delivery tracking is now available.")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Enable or disable SNS/SQS notifications')
    parser.add_argument('--enable', action='store_true', help='Enable notifications')
    parser.add_argument('--disable', action='store_true', help='Disable notifications')
    
    args = parser.parse_args()
    
    if args.enable and args.disable:
        print("❌ Error: Cannot both enable and disable at the same time.")
    elif args.enable:
        enable_all_notifications()
    elif args.disable:
        disable_all_notifications()
    else:
        # Check status
        status = "DISABLED" if os.environ.get('DISABLE_SNS_NOTIFICATIONS') == 'true' else "ENABLED"
        print(f"SNS/SQS Notification Status: {status}")
        print("Use --enable or --disable to change the status.")
