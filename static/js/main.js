// Main JavaScript for Bulk Email Scheduler

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
    
    // Initialize popovers
    const popoverTriggerList = document.querySelectorAll('[data-bs-toggle="popover"]');
    const popoverList = [...popoverTriggerList].map(popoverTriggerEl => new bootstrap.Popover(popoverTriggerEl));
    
    // Auto-hide flash messages after 5 seconds
    setTimeout(function() {
        const flashMessages = document.querySelectorAll('.alert-dismissible');
        flashMessages.forEach(function(message) {
            const alert = new bootstrap.Alert(message);
            alert.close();
        });
    }, 5000);
    
    // Form validation
    const forms = document.querySelectorAll('.needs-validation');
    Array.prototype.slice.call(forms).forEach(function(form) {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });
    
    // Template variable insertion for email editor
    const templateVariables = document.querySelectorAll('.template-variable');
    templateVariables.forEach(function(variable) {
        variable.addEventListener('click', function() {
            const variableName = this.dataset.variable;
            const targetId = this.dataset.target;
            const targetElement = document.getElementById(targetId);
            
            if (targetElement) {
                if (targetElement.tagName === 'TEXTAREA') {
                    // Insert at cursor position
                    const startPos = targetElement.selectionStart;
                    const endPos = targetElement.selectionEnd;
                    targetElement.value = targetElement.value.substring(0, startPos) + 
                                          '${' + variableName + '}' + 
                                          targetElement.value.substring(endPos);
                    // Set cursor position after the inserted variable
                    targetElement.selectionStart = startPos + variableName.length + 3; // +3 for "${" and "}"
                    targetElement.selectionEnd = startPos + variableName.length + 3;
                    targetElement.focus();
                } else if (targetElement.classList.contains('ck-editor__editable')) {
                    // For CKEditor instances
                    const editorInstance = CKEDITOR.instances[targetId];
                    if (editorInstance) {
                        editorInstance.insertText('${' + variableName + '}');
                    }
                }
            }
        });
    });
    
    // Confirmation dialogs
    const confirmationButtons = document.querySelectorAll('[data-confirm]');
    confirmationButtons.forEach(function(button) {
        button.addEventListener('click', function(event) {
            if (!confirm(this.dataset.confirm)) {
                event.preventDefault();
            }
        });
    });
    
    // Date picker initialization
    const datePickers = document.querySelectorAll('.datepicker');
    if (datePickers.length > 0) {
        datePickers.forEach(function(picker) {
            flatpickr(picker, {
                enableTime: true,
                dateFormat: "Y-m-d H:i",
                minDate: "today",
                time_24hr: true
            });
        });
    }
    
    // File input custom display
    const fileInputs = document.querySelectorAll('.custom-file-input');
    fileInputs.forEach(function(input) {
        input.addEventListener('change', function(e) {
            const fileName = this.files[0].name;
            const nextSibling = this.nextElementSibling;
            nextSibling.innerText = fileName;
        });
    });
    
    // Campaign status update
    const refreshStatusButtons = document.querySelectorAll('.refresh-status');
    refreshStatusButtons.forEach(function(button) {
        button.addEventListener('click', function() {
            const campaignId = this.dataset.campaignId;
            const statusElement = document.getElementById('campaign-status-' + campaignId);
            const spinnerElement = this.querySelector('.spinner-border');
            const iconElement = this.querySelector('.bi-arrow-clockwise');
            
            // Show spinner
            if (spinnerElement && iconElement) {
                spinnerElement.classList.remove('d-none');
                iconElement.classList.add('d-none');
            }
            
            // Fetch updated status
            fetch('/api/campaigns/' + campaignId + '/status')
                .then(response => response.json())
                .then(data => {
                    if (statusElement) {
                        // Update status display
                        statusElement.textContent = data.status.replace('_', ' ').charAt(0).toUpperCase() + data.status.replace('_', ' ').slice(1);
                        statusElement.className = 'campaign-status status-' + data.status;
                    }
                    
                    // Hide spinner
                    if (spinnerElement && iconElement) {
                        spinnerElement.classList.add('d-none');
                        iconElement.classList.remove('d-none');
                    }
                })
                .catch(error => {
                    console.error('Error fetching campaign status:', error);
                    // Hide spinner
                    if (spinnerElement && iconElement) {
                        spinnerElement.classList.add('d-none');
                        iconElement.classList.remove('d-none');
                    }
                });
        });
    });
    
    // Test email sending functionality
    const testEmailForm = document.getElementById('testEmailForm');
    if (testEmailForm) {
        testEmailForm.addEventListener('submit', function(event) {
            event.preventDefault();
            
            const campaignId = this.dataset.campaignId;
            const emailInput = document.getElementById('testEmailAddress');
            const submitButton = document.getElementById('sendTestEmailBtn');
            const resultDiv = document.getElementById('testEmailResult');
            
            if (!emailInput.value) {
                resultDiv.innerHTML = '<div class="alert alert-danger">Please enter an email address</div>';
                resultDiv.style.display = 'block';
                return;
            }
            
            // Disable button and show spinner
            submitButton.disabled = true;
            submitButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Sending...';
            
            // Send the test email
            fetch('/api/campaigns/' + campaignId + '/test-email', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ email: emailInput.value })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    resultDiv.innerHTML = '<div class="alert alert-success">' + data.message + '</div>';
                } else {
                    resultDiv.innerHTML = '<div class="alert alert-danger">' + data.message + '</div>';
                }
                
                resultDiv.style.display = 'block';
                submitButton.disabled = false;
                submitButton.innerHTML = 'Send Test';
            })
            .catch(error => {
                resultDiv.innerHTML = '<div class="alert alert-danger">An error occurred while sending the test email.</div>';
                resultDiv.style.display = 'block';
                submitButton.disabled = false;
                submitButton.innerHTML = 'Send Test';
            });
        });
    }
});
