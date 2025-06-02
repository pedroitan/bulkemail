"""
Recipient List Verification Routes

This module implements verification functionality for recipient lists,
allowing verification of email addresses in a list without requiring
the list to be associated with a campaign.
"""

import io
import csv
import threading
import os
from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app, make_response
from flask import copy_current_request_context
from sqlalchemy import select
from datetime import datetime
from models import db, EmailRecipient, RecipientList, recipient_list_items, EmailCampaign
from email_verification import EmailVerifier

# Routes to be added to recipient_lists_bp
def register_verification_routes(recipient_lists_bp):
    """Register verification routes with the recipient_lists_bp"""
    
    @recipient_lists_bp.route('/recipient-lists/<int:list_id>/verify', methods=['GET', 'POST'])
    def verify_recipient_list(list_id):
        """Verify email addresses in a recipient list without requiring a campaign"""
        recipient_list = RecipientList.query.get_or_404(list_id)
        
        if request.method == 'POST':
            # Get all recipients for this list
            stmt = db.select(EmailRecipient).join(
                recipient_list_items,
                (EmailRecipient.id == recipient_list_items.c.recipient_id) &
                (recipient_list_items.c.list_id == list_id)
            )
            recipients = db.session.execute(stmt).scalars().all()
            
            if not recipients:
                flash('No recipients found in this list.', 'warning')
                return redirect(url_for('recipient_lists_bp.view_recipient_list', list_id=list_id))
            
            # Get list of email addresses
            emails = [r.email for r in recipients]
            
            # Set verification status to In Progress
            recipient_list.verification_status = 'In Progress'
            db.session.commit()
            
            # Check if we're running on Render (production) or locally
            is_production = os.environ.get('RENDER', False) or os.environ.get('PRODUCTION', False)
            
            # Create a local EmailVerifier if the app doesn't have one
            # This ensures we don't depend on the app's email_verifier which might expect campaigns
            try:
                verifier = current_app.email_verifier
            except AttributeError:
                verifier = EmailVerifier()
                
            # If on Render (production), run synchronously to avoid background thread issues
            if is_production:
                # Run verification synchronously on Render
                print(f"Running verification synchronously for {len(emails)} emails on Render")
                results = verifier.batch_verify(emails)
                
                # Update recipient records with verification results
                for status, email_list in results.items():
                    for email in email_list:
                        recipient = EmailRecipient.query.filter_by(email=email).first()
                        
                        if recipient:
                            recipient.is_verified = (status == 'valid')
                            recipient.verification_result = status
                            recipient.verification_date = datetime.utcnow()
                
                db.session.commit()
                
                # Update list verification status
                recipient_list.verification_status = 'Complete'
                db.session.commit()
                
                flash(f'Email verification completed for {len(emails)} recipients.', 'success')
            else:
                # Start verification in background when running locally
                @copy_current_request_context
                def verify_emails_task():
                    # Use our local verifier or the app's verifier
                    try:
                        verifier = current_app.email_verifier
                    except AttributeError:
                        verifier = EmailVerifier()
                    
                    results = verifier.batch_verify(emails)
                    
                    # Update recipient records with verification results
                    with current_app.app_context():
                        for status, email_list in results.items():
                            for email in email_list:
                                recipient = EmailRecipient.query.filter_by(email=email).first()
                                
                                if recipient:
                                    recipient.is_verified = (status == 'valid')
                                    recipient.verification_result = status
                                    recipient.verification_date = datetime.utcnow()
                        
                        db.session.commit()
                        
                        # Update list verification status
                        recipient_list.verification_status = 'Complete'
                        db.session.commit()
                
                # Start verification in a separate thread
                verify_thread = threading.Thread(target=verify_emails_task)
                verify_thread.daemon = True
                verify_thread.start()
                
                flash(f'Email verification started for {len(emails)} recipients. This may take a few minutes.', 'info')
            
            # Return to the verification results page
            # Note: Status messages are set in the verification logic above
            return redirect(url_for('recipient_lists_bp.view_verification_results', list_id=list_id))
        
        return render_template('verify_recipients_list.html', recipient_list=recipient_list)

    @recipient_lists_bp.route('/recipient-lists/<int:list_id>/verification-results', methods=['GET'])
    def view_verification_results(list_id):
        """View verification results for a recipient list"""
        recipient_list = RecipientList.query.get_or_404(list_id)
        
        # Get all recipients for this list
        stmt = db.select(EmailRecipient).join(
            recipient_list_items,
            (EmailRecipient.id == recipient_list_items.c.recipient_id) &
            (recipient_list_items.c.list_id == list_id)
        )
        recipients = db.session.execute(stmt).scalars().all()
        
        # Calculate stats
        stats = {
            'total': len(recipients),
            'valid': 0,
            'invalid': 0,
            'risky': 0,
            'unverified': 0
        }
        
        for recipient in recipients:
            if not recipient.verification_result:
                stats['unverified'] += 1
            elif recipient.verification_result == 'valid':
                stats['valid'] += 1
            elif recipient.verification_result == 'invalid':
                stats['invalid'] += 1
            elif recipient.verification_result == 'risky':
                stats['risky'] += 1
        
        return render_template(
            'verify_recipients_list_results.html',
            recipient_list=recipient_list,
            recipients=recipients,
            stats=stats
        )

    @recipient_lists_bp.route('/recipient-lists/<int:list_id>/verification-download', methods=['GET'])
    def download_verification_report(list_id):
        """Generate and download a verification report for a recipient list"""
        recipient_list = RecipientList.query.get_or_404(list_id)
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Email', 'Name', 'Verification Status', 'Verification Date'])
        
        # Get all recipients for this list
        stmt = db.select(EmailRecipient).join(
            recipient_list_items,
            (EmailRecipient.id == recipient_list_items.c.recipient_id) &
            (recipient_list_items.c.list_id == list_id)
        )
        recipients = db.session.execute(stmt).scalars().all()
        
        # Write data
        for recipient in recipients:
            status = recipient.verification_result or 'unverified'
            verification_date = ''
            if recipient.verification_date:
                verification_date = recipient.verification_date.strftime('%Y-%m-%d %H:%M:%S')
                
            writer.writerow([
                recipient.email, 
                recipient.name or '', 
                status, 
                verification_date
            ])
        
        # Prepare response
        response = make_response(output.getvalue())
        response.headers["Content-Disposition"] = f"attachment; filename=verification_report_{recipient_list.name}.csv"
        response.headers["Content-type"] = "text/csv"
        
        return response

    @recipient_lists_bp.route('/recipient-lists/<int:list_id>/remove-invalid', methods=['POST'])
    def remove_invalid_recipients(list_id):
        """Remove invalid recipients from a list based on verification results"""
        recipient_list = RecipientList.query.get_or_404(list_id)
        
        # Get all invalid recipients for this list
        stmt = db.select(EmailRecipient).join(
            recipient_list_items,
            (EmailRecipient.id == recipient_list_items.c.recipient_id) &
            (recipient_list_items.c.list_id == list_id)
        ).where(EmailRecipient.verification_result == 'invalid')
        
        invalid_recipients = db.session.execute(stmt).scalars().all()
        
        # Count before removal
        invalid_count = len(invalid_recipients)
        
        # Remove invalid recipients from the list
        for recipient in invalid_recipients:
            delete_stmt = recipient_list_items.delete().where(
                (recipient_list_items.c.list_id == list_id) &
                (recipient_list_items.c.recipient_id == recipient.id)
            )
            db.session.execute(delete_stmt)
        
        db.session.commit()
        
        flash(f'Removed {invalid_count} invalid recipients from the list.', 'success')
        return redirect(url_for('recipient_lists_bp.view_verification_results', list_id=list_id))
