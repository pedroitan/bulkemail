"""
Recipient List Management Module

This module implements functions for managing reusable recipient lists, 
including creating, viewing, editing, and exporting lists.
It also handles tagging recipients with bounce information to prevent
sending to problematic email addresses in future campaigns.
"""

import os
import io
import csv
import json
import pandas as pd
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, current_app, send_file
from werkzeug.utils import secure_filename
from datetime import datetime
from models import db, EmailRecipient, RecipientList, recipient_list_items
from forms import RecipientListForm, ExportRecipientsForm, UploadRecipientsForm

# Create blueprint for recipient list routes
recipient_lists_bp = Blueprint('recipient_lists_bp', __name__)

@recipient_lists_bp.route('/recipient-lists')
def recipient_lists():
    """List all recipient lists"""
    lists = RecipientList.query.order_by(RecipientList.created_at.desc()).all()
    return render_template('recipient_lists.html', recipient_lists=lists)

@recipient_lists_bp.route('/recipient-lists/create', methods=['GET', 'POST'])
def create_recipient_list():
    """Create a new recipient list"""
    form = RecipientListForm()
    
    if form.validate_on_submit():
        recipient_list = RecipientList(
            name=form.name.data,
            description=form.description.data
        )
        db.session.add(recipient_list)
        db.session.commit()
        
        flash('Recipient list created successfully!', 'success')
        return redirect(url_for('recipient_lists_bp.view_recipient_list', list_id=recipient_list.id))
    
    return render_template('create_recipient_list.html', form=form)

@recipient_lists_bp.route('/recipient-lists/<int:list_id>', methods=['GET'])
def view_recipient_list(list_id):
    """View details of a recipient list"""
    recipient_list = RecipientList.query.get_or_404(list_id)
    
    # Update stats before displaying
    recipient_list.update_stats()
    db.session.commit()
    
    # Get recipients with pagination
    page = request.args.get('page', 1, type=int)
    per_page = 100  # Show 100 recipients per page
    recipients_query = db.session.query(EmailRecipient).join(
        recipient_list_items,
        (recipient_list_items.c.recipient_id == EmailRecipient.id) & 
        (recipient_list_items.c.list_id == list_id)
    ).order_by(EmailRecipient.email)
    
    # Apply any filters
    status_filter = request.args.get('status', None)
    if status_filter:
        recipients_query = recipients_query.filter(EmailRecipient.global_status == status_filter)
        
    # Paginate results
    pagination = recipients_query.paginate(page=page, per_page=per_page)
    
    return render_template('recipient_list_detail.html', 
                          recipient_list=recipient_list, 
                          recipients=pagination.items,
                          pagination=pagination)

@recipient_lists_bp.route('/recipient-lists/<int:list_id>/edit', methods=['GET', 'POST'])
def edit_recipient_list(list_id):
    """Edit a recipient list"""
    recipient_list = RecipientList.query.get_or_404(list_id)
    form = RecipientListForm(obj=recipient_list)
    
    if form.validate_on_submit():
        recipient_list.name = form.name.data
        recipient_list.description = form.description.data
        recipient_list.updated_at = datetime.now()
        
        db.session.commit()
        flash('Recipient list updated successfully!', 'success')
        return redirect(url_for('recipient_lists_bp.view_recipient_list', list_id=recipient_list.id))
    
    return render_template('create_recipient_list.html', form=form, recipient_list=recipient_list)

@recipient_lists_bp.route('/recipient-lists/<int:list_id>/delete', methods=['POST'])
def delete_recipient_list(list_id):
    """Delete a recipient list"""
    recipient_list = RecipientList.query.get_or_404(list_id)
    
    try:
        # Remove the list but keep the actual recipients
        db.session.delete(recipient_list)
        db.session.commit()
        flash('Recipient list deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting recipient list: {str(e)}', 'danger')
    
    return redirect(url_for('recipient_lists_bp.recipient_lists'))

@recipient_lists_bp.route('/recipient-lists/<int:list_id>/add-recipients', methods=['GET', 'POST'])
def add_recipients_to_list(list_id):
    """Add recipients to a list by uploading a file"""
    recipient_list = RecipientList.query.get_or_404(list_id)
    form = UploadRecipientsForm()
    
    if form.validate_on_submit():
        try:
            # Get uploaded file
            file = form.file.data
            filename = secure_filename(file.filename)
            file_path = os.path.join('/tmp', filename)
            file.save(file_path)
            
            # Process the file and add recipients to the list
            added_count = process_recipient_file(file_path, recipient_list)
            
            # Clean up temporary file
            os.unlink(file_path)
            
            flash(f'Successfully added {added_count} recipients to the list!', 'success')
            return redirect(url_for('recipient_lists_bp.view_recipient_list', list_id=list_id))
            
        except Exception as e:
            flash(f'Error processing file: {str(e)}', 'danger')
    
    return render_template('upload_recipients.html', form=form, campaign=None, recipient_list=recipient_list)

@recipient_lists_bp.route('/recipient-lists/<int:list_id>/remove-recipient/<int:recipient_id>', methods=['POST'])
def remove_recipient_from_list(list_id, recipient_id):
    """Remove a recipient from a list"""
    recipient_list = RecipientList.query.get_or_404(list_id)
    recipient = EmailRecipient.query.get_or_404(recipient_id)
    
    try:
        # Remove the association, not the recipient itself
        stmt = recipient_list_items.delete().where(
            (recipient_list_items.c.list_id == list_id) & 
            (recipient_list_items.c.recipient_id == recipient_id)
        )
        db.session.execute(stmt)
        db.session.commit()
        
        # Update list stats
        recipient_list.update_stats()
        db.session.commit()
        
        flash(f'Recipient {recipient.email} removed from list!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error removing recipient: {str(e)}', 'danger')
    
    return redirect(url_for('recipient_lists_bp.view_recipient_list', list_id=list_id))

@recipient_lists_bp.route('/recipient-lists/<int:list_id>/export', methods=['GET', 'POST'])
def export_recipient_list(list_id):
    """Export a recipient list to CSV or Excel"""
    recipient_list = RecipientList.query.get_or_404(list_id)
    form = ExportRecipientsForm()
    
    # Handle direct format requests from URL parameter
    format_param = request.args.get('format')
    if format_param in ['csv', 'xlsx']:
        return generate_export_file(recipient_list, format_param)
    
    if form.validate_on_submit():
        format_type = form.export_format.data
        
        # Apply filters based on form selections
        include_bounced = form.include_bounced.data
        include_complained = form.include_complained.data
        include_suppressed = form.include_suppressed.data
        
        return generate_export_file(
            recipient_list, 
            format_type, 
            include_bounced, 
            include_complained, 
            include_suppressed
        )
    
    return render_template('export_recipients.html', form=form, recipient_list=recipient_list)

def process_recipient_file(file_path, recipient_list):
    """
    Process a CSV or Excel file of recipients and add them to the specified list.
    Returns the number of recipients added to the list.
    """
    # Determine file type and read accordingly
    if file_path.endswith('.csv'):
        df = pd.read_csv(file_path)
    elif file_path.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(file_path)
    else:
        raise ValueError("Unsupported file format. Please use CSV or Excel.")
    
    # Clean column names (lowercase, strip whitespace)
    df.columns = [col.lower().strip() for col in df.columns]
    
    # Ensure required columns exist
    if 'email' not in df.columns:
        raise ValueError("File must contain an 'email' column")
    
    # Clean email addresses
    df['email'] = df['email'].str.lower().str.strip()
    
    # Optional name column
    has_name = 'name' in df.columns
    
    # Process custom fields (any columns other than email and name)
    custom_fields = [col for col in df.columns if col not in ['email', 'name']]
    
    # Track how many recipients were added to the list
    added_count = 0
    
    # Process each row
    for _, row in df.iterrows():
        email = row['email']
        
        # Skip empty emails
        if not email or pd.isna(email):
            continue
            
        # Check if recipient already exists
        recipient = EmailRecipient.query.filter_by(email=email).first()
        
        if not recipient:
            # Create a placeholder campaign_id - it will be used only for creating the recipient
            # We need this because recipients are always associated with a campaign
            # Use -999 as a special ID to indicate this is a placeholder
            custom_data = {}
            for field in custom_fields:
                if not pd.isna(row[field]):
                    custom_data[field] = row[field]
            
            # Create new recipient
            recipient = EmailRecipient(
                campaign_id=-999,  # Placeholder
                email=email,
                name=row['name'] if has_name and not pd.isna(row['name']) else None,
                status='pending',
                global_status='active'  # Default to active
            )
            
            # Add custom data if any
            if custom_data:
                recipient.set_custom_data(custom_data)
                
            db.session.add(recipient)
            db.session.flush()  # Get an ID assigned without committing
        
        # Check if recipient is already in this list
        assoc = db.session.query(recipient_list_items).filter_by(
            list_id=recipient_list.id, 
            recipient_id=recipient.id
        ).first()
        
        if not assoc:
            # Add to the list
            stmt = recipient_list_items.insert().values(
                list_id=recipient_list.id,
                recipient_id=recipient.id
            )
            db.session.execute(stmt)
            added_count += 1
    
    # Commit all changes
    db.session.commit()
    
    # Update list stats
    recipient_list.update_stats()
    db.session.commit()
    
    return added_count

def generate_export_file(recipient_list, format_type, include_bounced=False, include_complained=False, include_suppressed=False):
    """Generate a CSV or Excel export file for a recipient list"""
    # Start with all recipients in the list
    recipients_query = db.session.query(EmailRecipient).join(
        recipient_list_items,
        (recipient_list_items.c.recipient_id == EmailRecipient.id) & 
        (recipient_list_items.c.list_id == recipient_list.id)
    )
    
    # Apply filters based on parameters
    status_filters = ['active']
    if include_bounced:
        status_filters.append('bounced')
    if include_complained:
        status_filters.append('complained')
    if include_suppressed:
        status_filters.append('suppressed')
    
    recipients_query = recipients_query.filter(EmailRecipient.global_status.in_(status_filters))
    
    # Get all recipients matching the filters
    recipients = recipients_query.all()
    
    # Prepare data for export
    data = []
    for recipient in recipients:
        # Start with basic info
        row = {
            'email': recipient.email,
            'name': recipient.name or '',
            'status': recipient.global_status,
        }
        
        # Add tracking stats
        row.update({
            'open_count': recipient.open_count or 0,
            'click_count': recipient.click_count or 0,
            'last_opened': recipient.last_opened_at.strftime('%Y-%m-%d %H:%M:%S') if recipient.last_opened_at else '',
            'last_clicked': recipient.last_clicked_at.strftime('%Y-%m-%d %H:%M:%S') if recipient.last_clicked_at else '',
        })
        
        # Add bounce info if available
        if recipient.bounce_type:
            row.update({
                'bounce_type': recipient.bounce_type,
                'bounce_subtype': recipient.bounce_subtype,
                'bounce_time': recipient.bounce_time.strftime('%Y-%m-%d %H:%M:%S') if recipient.bounce_time else '',
                'bounce_diagnostic': recipient.bounce_diagnostic or '',
            })
            
        # Add custom data if available
        custom_data = recipient.get_custom_data() if recipient.custom_data else {}
        for key, value in custom_data.items():
            # Add prefix to avoid potential column name conflicts
            row[f'custom_{key}'] = value
            
        data.append(row)
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Generate the appropriate file format
    if format_type == 'csv':
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f"{recipient_list.name.replace(' ', '_')}_export_{datetime.now().strftime('%Y%m%d')}.csv"
        )
    else:  # xlsx format
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Recipients', index=False)
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f"{recipient_list.name.replace(' ', '_')}_export_{datetime.now().strftime('%Y%m%d')}.xlsx"
        )
