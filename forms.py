from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, TextAreaField, DateTimeField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, Length, Optional
from datetime import datetime
import os
from dotenv import load_dotenv, find_dotenv

# Always reload environment variables to get the latest values
load_dotenv(find_dotenv(), override=True)

# Get domains from environment, with vendo147.com as the default first choice if available
domains = os.environ.get('SENDER_DOMAINS', '').split(',')
domain_choices = []
for domain in domains:
    if domain.strip():
        domain_choices.append((domain.strip(), domain.strip()))

class CampaignForm(FlaskForm):
    name = StringField('Campaign Name', validators=[DataRequired(), Length(max=100)])
    subject = StringField('Email Subject', validators=[DataRequired(), Length(max=200)])
    sender_name = StringField('Sender Name', validators=[Length(max=100)])
    sender_domain = SelectField('Sender Domain', choices=domain_choices, validators=[DataRequired()])
    sender_email = StringField('Sender Email Username', validators=[DataRequired(), Length(max=100)],
                              description='Username part of the email (before the @)')
    scheduled_time = DateTimeField('Scheduled Time', validators=[Optional()], 
                                  format='%Y-%m-%dT%H:%M', default=datetime.now)
    body_html = TextAreaField('Email Body (HTML)', validators=[DataRequired()])
    body_text = TextAreaField('Email Body (Plain Text)', validators=[Optional()])
    submit = SubmitField('Create Campaign')

class UploadRecipientsForm(FlaskForm):
    file = FileField('Recipients File (CSV or Excel)', 
                    validators=[
                        FileRequired(),
                        FileAllowed(['csv', 'xlsx', 'xls'], 'CSV or Excel files only!')
                    ])
    submit = SubmitField('Upload')
