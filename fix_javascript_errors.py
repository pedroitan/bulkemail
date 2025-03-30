#!/usr/bin/env python
"""
Script to fix JavaScript errors in the campaign detail template
by directly adding jQuery handlers instead of using onclick attributes
"""

import os

# Path to the campaign detail template
template_path = os.path.join('templates', 'campaign_detail.html')

# New content for the template
new_content = """{% extends "base.html" %}

{% block title %}Bulk Email Campaign Details{% endblock %}

{% block content %}
<div class="container-fluid">
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2><i class="bi bi-envelope-open me-2"></i>{{ campaign.name }}</h2>
        <div class="btn-group" role="group">
            <a href="{{ url_for('edit_campaign', campaign_id=campaign.id) }}" class="btn btn-outline-secondary">
                <i class="bi bi-pencil me-2"></i>Edit Campaign
            </a>
            <form action="{{ url_for('start_campaign_form', campaign_id=campaign.id) }}" method="POST" style="display: inline-block;">
                <button type="submit" class="btn btn-success">
                    <i class="bi bi-send me-2"></i>Start Sending
                </button>
            </form>
            <a href="{{ url_for('campaigns') }}" class="btn btn-outline-secondary">
                <i class="bi bi-arrow-left me-2"></i>Back to Campaigns
            </a>
        </div>
    </div>

    <div class="row">
        <div class="col-md-8">
            <!-- Campaign Details -->
            <div class="card mb-4">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <h5 class="card-title mb-0">Campaign Details</h5>
                    <span class="campaign-status status-{{ campaign.status }}">
                        {{ campaign.status|replace('_', ' ')|title }}
                    </span>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-6">
                            <p><strong>Subject:</strong> {{ campaign.subject }}</p>
                            <p><strong>Created:</strong> {{ campaign.created_at.strftime('%Y-%m-%d %H:%M') }}</p>
                            {% if campaign.scheduled_at %}
                            <p><strong>Scheduled:</strong> {{ campaign.scheduled_at.strftime('%Y-%m-%d %H:%M') }}</p>
                            {% endif %}
                        </div>
                        <div class="col-md-6">
                            <p><strong>Recipients:</strong> {{ recipients|length }}</p>
                            <p><strong>Status:</strong> {{ campaign.status|replace('_', ' ')|title }}</p>
                            {% if campaign.started_at %}
                            <p><strong>Started:</strong> {{ campaign.started_at.strftime('%Y-%m-%d %H:%M') }}</p>
                            {% endif %}
                        </div>
                    </div>
                </div>
            </div>

            <!-- Campaign Content -->
            <div class="card mb-4">
                <div class="card-header">
                    <h5 class="card-title mb-0">Campaign Content</h5>
                </div>
                <div class="card-body">
                    <div class="mb-3">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <h6 class="mb-0">HTML Content</h6>
                            <button type="button" class="btn btn-sm btn-outline-primary test-email-btn" data-bs-toggle="modal" data-bs-target="#testEmailModal">
                                <i class="bi bi-envelope-paper me-1"></i> Send Test Email
                            </button>
                        </div>
                        <div class="border p-3 rounded" style="background-color: #f8f9fa;">
                            <div class="html-preview">
                                {{ campaign.body_html|safe }}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="col-md-4">
            <!-- Campaign Actions -->
            <div class="card mb-4">
                <div class="card-header">
                    <h5 class="card-title mb-0">Actions</h5>
                </div>
                <div class="card-body">
                    <div class="d-grid gap-2">
                        <a href="{{ url_for('edit_campaign', campaign_id=campaign.id) }}" class="btn btn-outline-primary">
                            <i class="bi bi-pencil me-2"></i>Edit Campaign
                        </a>
                        <form action="{{ url_for('start_campaign_form', campaign_id=campaign.id) }}" method="POST">
                            <button type="submit" class="btn btn-success w-100">
                                <i class="bi bi-send me-2"></i>Start Sending
                            </button>
                        </form>
                        <a href="{{ url_for('upload_recipients', campaign_id=campaign.id) }}" class="btn btn-outline-primary">
                            <i class="bi bi-upload me-2"></i>Upload Recipients
                        </a>
                        <form action="{{ url_for('reset_campaign', campaign_id=campaign.id) }}" method="POST">
                            <button type="submit" class="btn btn-outline-warning w-100">
                                <i class="bi bi-arrow-counterclockwise me-2"></i>Reset Campaign
                            </button>
                        </form>
                        <form action="{{ url_for('delete_campaign', campaign_id=campaign.id) }}" method="POST" onsubmit="return confirm('Are you sure you want to delete this campaign?');">
                            <button type="submit" class="btn btn-outline-danger w-100">
                                <i class="bi bi-trash me-2"></i>Delete Campaign
                            </button>
                        </form>
                    </div>
                </div>
            </div>

            <!-- Campaign Stats -->
            <div class="card mb-4">
                <div class="card-header">
                    <h5 class="card-title mb-0">Statistics</h5>
                </div>
                <div class="card-body">
                    <div class="row text-center">
                        <div class="col-6 mb-3">
                            <div class="h4">{{ stats.sent|default(0) }}</div>
                            <div class="text-muted">Sent</div>
                        </div>
                        <div class="col-6 mb-3">
                            <div class="h4">{{ stats.delivered|default(0) }}</div>
                            <div class="text-muted">Delivered</div>
                        </div>
                        <div class="col-6 mb-3">
                            <div class="h4">{{ stats.bounced|default(0) }}</div>
                            <div class="text-muted">Bounced</div>
                        </div>
                        <div class="col-6 mb-3">
                            <div class="h4">{{ stats.complained|default(0) }}</div>
                            <div class="text-muted">Complaints</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Recipients Table -->
    <div class="card mb-4">
        <div class="card-header d-flex justify-content-between align-items-center">
            <h5 class="card-title mb-0">Recipients</h5>
            <a href="{{ url_for('upload_recipients', campaign_id=campaign.id) }}" class="btn btn-sm btn-outline-primary">
                <i class="bi bi-upload me-1"></i>Upload Recipients
            </a>
        </div>
        <div class="card-body">
            {% if recipients %}
            <div class="table-responsive">
                <table class="table table-striped table-hover" id="recipients-table">
                    <thead>
                        <tr>
                            <th>Email</th>
                            <th>Status</th>
                            <th>Delivery Status</th>
                        </tr>
                    </thead>
                    <tbody id="recipientsTableBody">
                        {% for recipient in recipients %}
                        <tr>
                            <td>{{ recipient.email }}</td>
                            <td>{{ recipient.status }}</td>
                            <td>
                                {% if recipient.delivery_status == 'delivered' %}
                                <span class="badge bg-success">Delivered</span>
                                {% elif recipient.delivery_status == 'bounced' %}
                                <span class="badge bg-danger">Bounced</span>
                                {% elif recipient.delivery_status == 'complained' %}
                                <span class="badge bg-warning text-dark">Complained</span>
                                {% elif recipient.delivery_status == 'sent' %}
                                <span class="badge bg-primary">Sent</span>
                                {% else %}
                                <span class="badge bg-secondary">{{ recipient.delivery_status }}</span>
                                {% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            {% else %}
            <div class="alert alert-info">
                No recipients added yet. <a href="{{ url_for('upload_recipients', campaign_id=campaign.id) }}">Upload recipients</a> to send this campaign.
            </div>
            {% endif %}
        </div>
    </div>
</div>

<!-- Test Email Modal -->
<div class="modal fade" id="testEmailModal" tabindex="-1" aria-labelledby="testEmailModalLabel" aria-hidden="true">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Send Test Email</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
                <form action="{{ url_for('send_test_email_form', campaign_id=campaign.id) }}" method="POST" id="testEmailForm">
                    <div class="mb-3">
                        <label for="testEmail" class="form-label">Recipient Email:</label>
                        <input type="email" class="form-control" id="testEmail" name="email" placeholder="Enter email">
                    </div>
                    <div class="mb-3">
                        <small class="text-muted">Test Bounce Simulator Addresses:</small>
                        <div class="d-flex flex-wrap gap-2 mt-1">
                            <button type="button" class="btn btn-sm btn-outline-secondary simulator-address" data-email="bounce@simulator.amazonses.com">Bounce</button>
                            <button type="button" class="btn btn-sm btn-outline-secondary simulator-address" data-email="complaint@simulator.amazonses.com">Complaint</button>
                            <button type="button" class="btn btn-sm btn-outline-secondary simulator-address" data-email="success@simulator.amazonses.com">Success</button>
                        </div>
                    </div>
                </form>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                <button type="submit" form="testEmailForm" class="btn btn-primary">Send Test Email</button>
            </div>
        </div>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script>
$(document).ready(function() {
    // Auto-refresh functionality for recipients table
    function refreshRecipientsTable() {
        $.ajax({
            url: "{{ url_for('get_campaign_recipients', campaign_id=campaign.id) }}",
            type: "GET",
            dataType: "json",
            success: function(data) {
                updateRecipientsTable(data);
            },
            error: function(jqXHR, textStatus, errorThrown) {
                console.error("Error fetching recipients:", textStatus, errorThrown);
            }
        });
    }
    
    function updateRecipientsTable(recipients) {
        const tableBody = $("#recipientsTableBody");
        if (!tableBody.length) {
            return;
        }
        
        // Clear existing rows
        tableBody.empty();
        
        // Add rows for each recipient
        recipients.forEach(function(recipient) {
            const row = $("<tr></tr>");
            
            row.append($("<td></td>").text(recipient.email));
            row.append($("<td></td>").text(recipient.status));
            
            // Delivery status with appropriate badge
            const deliveryStatusCell = $("<td></td>");
            const deliveryStatus = recipient.delivery_status || "pending";
            
            let badgeClass = "badge bg-secondary";
            
            if (deliveryStatus === "delivered") {
                badgeClass = "badge bg-success";
            } else if (deliveryStatus === "bounced") {
                badgeClass = "badge bg-danger";
            } else if (deliveryStatus === "complained") {
                badgeClass = "badge bg-warning text-dark";
            } else if (deliveryStatus === "sent") {
                badgeClass = "badge bg-primary";
            }
            
            deliveryStatusCell.append(
                $("<span></span>")
                    .addClass(badgeClass)
                    .text(deliveryStatus)
            );
            
            row.append(deliveryStatusCell);
            
            // Add to table
            tableBody.append(row);
        });
    }
    
    // Set up the simulator address buttons
    $(".simulator-address").on("click", function() {
        const email = $(this).data("email");
        $("#testEmail").val(email);
    });
    
    // Start auto-refresh
    refreshRecipientsTable(); // Initial load
    setInterval(refreshRecipientsTable, 5000); // Refresh every 5 seconds
});
</script>
{% endblock %}"""

# Write the new content to the template file
with open(template_path, 'w') as f:
    f.write(new_content)

print("✅ Fixed JavaScript errors in campaign_detail.html")
