import os
import pandas as pd
from flask import current_app
from werkzeug.utils import secure_filename
import uuid

def allowed_file(filename):
    """Check if the file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def save_uploaded_file(file):
    """Save an uploaded file and return the path"""
    if not os.path.exists(current_app.config['UPLOAD_FOLDER']):
        os.makedirs(current_app.config['UPLOAD_FOLDER'])
    
    filename = secure_filename(file.filename)
    # Add unique identifier to prevent filename collisions
    unique_filename = f"{uuid.uuid4()}_{filename}"
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
    file.save(file_path)
    return file_path

def preview_file_data(file_path, max_rows=None):
    """Preview the data from a CSV or Excel file"""
    if file_path.endswith('.csv'):
        df = pd.read_csv(file_path, header=None, skipinitialspace=True)
    elif file_path.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(file_path, header=None, dtype=str)
    else:
        raise ValueError("Unsupported file format")
    
    # Rename the first column to 'email'
    df.columns = ['email']
    
    # Clean email addresses - multiple steps to ensure thorough cleaning
    df['email'] = (df['email']
                  .astype(str)
                  .str.replace(',', '')  # Remove all commas
                  .str.strip()           # Remove leading/trailing whitespace
                  .str.replace(r'\s+', '')  # Remove any internal whitespace
                  )
    
    # Remove any empty rows
    df = df[df['email'].str.len() > 0]
    
    # Convert to list of clean emails
    clean_emails = df['email'].tolist()
    
    return {
        'columns': ['email'],
        'rows': [{'email': email} for email in clean_emails],
        'total_rows': len(clean_emails)
    }

def validate_email_template(template):
    """
    Validate that the email template contains required placeholders
    and doesn't have any syntax errors
    """
    # Basic validation - you can extend this as needed
    try:
        from string import Template
        Template(template).safe_substitute({})
        return True, "Template is valid"
    except Exception as e:
        return False, f"Template validation error: {str(e)}"

def get_campaign_stats(campaign):
    """Get statistics for a campaign"""
    from models import EmailRecipient
    
    stats = {
        'total': EmailRecipient.query.filter_by(campaign_id=campaign.id).count(),
        'sent': EmailRecipient.query.filter_by(campaign_id=campaign.id, status='sent').count(),
        'pending': EmailRecipient.query.filter_by(campaign_id=campaign.id, status='pending').count(),
        'failed': EmailRecipient.query.filter_by(campaign_id=campaign.id, status='failed').count(),
    }
    
    return stats
