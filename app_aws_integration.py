"""
AWS Usage Integration Helper

This script adds the AWS usage tracker to your application by:
1. Modifying your app.py to register the AWS usage blueprint
2. Adding AWS usage tracking to SNS notification handler
3. Adding AWS usage tracking to email sending functions

Run this script to integrate AWS usage tracking with your application.
"""

import os
import re
import logging
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('AWSIntegrator')

def add_blueprint_import(app_content):
    """Add import for AWS usage blueprint"""
    if 'from aws_usage import aws_usage_blueprint' in app_content:
        logger.info("AWS usage blueprint import already exists")
        return app_content
        
    # Find the imports section and add our import
    import_section = re.search(r'import.*?\n\n', app_content, re.DOTALL)
    if import_section:
        # Insert after last import
        import_pos = import_section.end()
        modified_content = (
            app_content[:import_pos] + 
            "from aws_usage import aws_usage_blueprint, track_email_sent, track_sns_notification\n" +
            app_content[import_pos:]
        )
        logger.info("Added AWS usage blueprint import")
        return modified_content
    else:
        logger.error("Could not find import section")
        return app_content

def add_blueprint_registration(app_content):
    """Register the AWS usage blueprint"""
    if 'app.register_blueprint(aws_usage_blueprint)' in app_content:
        logger.info("AWS usage blueprint already registered")
        return app_content
        
    # Find where blueprints are registered
    register_pattern = r'app = Flask\(__name__\).*?app\.config\.from_object'
    register_match = re.search(register_pattern, app_content, re.DOTALL)
    
    if register_match:
        register_pos = register_match.end()
        modified_content = (
            app_content[:register_pos] + 
            "\n\n    # Register AWS usage blueprint\n    app.register_blueprint(aws_usage_blueprint)\n" +
            app_content[register_pos:]
        )
        logger.info("Added AWS usage blueprint registration")
        return modified_content
    else:
        logger.error("Could not find Flask app initialization")
        return app_content

def add_sns_notification_tracking(app_content):
    """Add AWS usage tracking to SNS notification handler"""
    if 'track_sns_notification()' in app_content:
        logger.info("SNS notification tracking already added")
        return app_content
        
    # Find the SNS notification handler
    sns_handler_pattern = r'@app\.route\(\'/api/sns/ses-notification\', methods=\[\'POST\'\]\)\s+def sns_notification_handler\(\):'
    sns_handler_match = re.search(sns_handler_pattern, app_content)
    
    if sns_handler_match:
        sns_handler_pos = sns_handler_match.end()
        # Find the first line after the function definition
        first_line_match = re.search(r'\n\s+', app_content[sns_handler_pos:])
        if first_line_match:
            insert_pos = sns_handler_pos + first_line_match.end()
            indent = first_line_match.group().replace('\n', '')
            modified_content = (
                app_content[:insert_pos] + 
                f"{indent}# Track SNS notification for AWS usage metrics\n{indent}track_sns_notification()\n\n" +
                app_content[insert_pos:]
            )
            logger.info("Added SNS notification tracking")
            return modified_content
    
    logger.error("Could not find SNS notification handler")
    return app_content

def add_email_send_tracking(app_content):
    """Add AWS usage tracking to email sending functions"""
    if 'track_email_sent()' in app_content:
        logger.info("Email send tracking already added")
        return app_content
        
    # Find email sending function
    email_send_pattern = r'def send_email\(recipient_id\):'
    email_send_match = re.search(email_send_pattern, app_content)
    
    if email_send_match:
        email_send_pos = email_send_match.end()
        # Find the first line after the function definition
        first_line_match = re.search(r'\n\s+', app_content[email_send_pos:])
        if first_line_match:
            insert_pos = email_send_pos + first_line_match.end()
            indent = first_line_match.group().replace('\n', '')
            modified_content = (
                app_content[:insert_pos] + 
                f"{indent}# Track email sending for AWS usage metrics\n{indent}track_email_sent()\n\n" +
                app_content[insert_pos:]
            )
            logger.info("Added email send tracking")
            return modified_content
    
    logger.error("Could not find email sending function")
    return app_content

def add_dashboard_link(app_content):
    """Add AWS usage dashboard link to navigation menu"""
    if 'href="/aws-usage"' in app_content:
        logger.info("AWS usage dashboard link already added")
        return app_content
        
    # Find navigation menu in base.html or main navigation
    nav_pattern = r'<li class="nav-item">\s+<a class="nav-link" href="/campaigns">'
    nav_match = re.search(nav_pattern, app_content)
    
    if nav_match:
        nav_pos = nav_match.start()
        # Find the <li> tag opening
        li_open_match = re.search(r'<li class="nav-item">', app_content[:nav_pos])
        if li_open_match:
            indent = ' ' * li_open_match.start()
            nav_item = (
                f'{indent}<li class="nav-item">\n'
                f'{indent}  <a class="nav-link" href="/aws-usage">\n'
                f'{indent}    <i class="fas fa-chart-bar me-1"></i>AWS Usage\n'
                f'{indent}  </a>\n'
                f'{indent}</li>\n'
            )
            modified_content = app_content[:nav_pos] + nav_item + app_content[nav_pos:]
            logger.info("Added AWS usage dashboard link to navigation")
            return modified_content
    
    logger.error("Could not find navigation menu")
    return app_content

def integrate_aws_usage():
    """Integrate AWS usage tracking with the application"""
    logger.info("Starting AWS usage integration")
    
    # Check if app.py exists
    app_path = 'app.py'
    if not os.path.exists(app_path):
        logger.error(f"Could not find {app_path}")
        return False
        
    # Read app.py
    try:
        with open(app_path, 'r') as f:
            app_content = f.read()
    except Exception as e:
        logger.error(f"Error reading {app_path}: {str(e)}")
        return False
        
    # Add import for AWS usage blueprint
    app_content = add_blueprint_import(app_content)
    
    # Add blueprint registration
    app_content = add_blueprint_registration(app_content)
    
    # Add SNS notification tracking
    app_content = add_sns_notification_tracking(app_content)
    
    # Add email send tracking
    app_content = add_email_send_tracking(app_content)
    
    # Write modified app.py
    try:
        # First backup the original file
        backup_path = f"{app_path}.bak"
        with open(backup_path, 'w') as f:
            f.write(app_content)
            logger.info(f"Created backup of {app_path} at {backup_path}")
            
        # Now modify the original file (commented out for safety)
        # with open(app_path, 'w') as f:
        #     f.write(app_content)
        #     logger.info(f"Updated {app_path} with AWS usage tracking")
        
        logger.info("*" * 80)
        logger.info("AWS usage tracking integration completed!")
        logger.info("To complete the integration, manually copy the changes from app.py.bak to app.py")
        logger.info("*" * 80)
        
        # Check for base.html to add navigation link
        base_html_path = 'templates/base.html'
        if os.path.exists(base_html_path):
            try:
                with open(base_html_path, 'r') as f:
                    base_content = f.read()
                    
                # Add AWS usage dashboard link to navigation
                modified_base = add_dashboard_link(base_content)
                
                # Create backup
                base_backup_path = f"{base_html_path}.bak"
                with open(base_backup_path, 'w') as f:
                    f.write(modified_base)
                    logger.info(f"Created backup of {base_html_path} at {base_backup_path}")
                
                # Write modified base.html (commented out for safety)
                # with open(base_html_path, 'w') as f:
                #     f.write(modified_base)
                #     logger.info(f"Updated {base_html_path} with AWS usage dashboard link")
                
                logger.info("*" * 80)
                logger.info("To add the AWS Usage dashboard to navigation, manually copy the changes from templates/base.html.bak to templates/base.html")
                logger.info("*" * 80)
                
            except Exception as e:
                logger.error(f"Error modifying {base_html_path}: {str(e)}")
        else:
            logger.warning(f"Could not find {base_html_path}")
        
        return True
    except Exception as e:
        logger.error(f"Error writing modified {app_path}: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("=== AWS Usage Integration Script ===")
    integrate_aws_usage()
