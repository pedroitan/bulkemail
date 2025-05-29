"""
Internationalization support for the Bulk Email Scheduler.

This module provides language detection and translation functionality using Flask-Babel.
It detects the user's preferred language from browser headers and geolocation,
while also allowing manual language selection that's saved in the user's session.
"""

from flask import request, session, g, redirect
from flask_babel import Babel

# Supported languages
LANGUAGES = {
    'en': 'English',
    'pt_BR': 'Português (Brasil)'
}

# Default language
DEFAULT_LANGUAGE = 'en'

# Initialize Babel
babel = Babel()

def get_locale():
    """
    Determine which language to use for the current request.
    Priority:
    1. User selected language stored in session
    2. Browser's preferred language
    3. Default to English
    """
    # If user has manually selected a language
    if 'language' in session:
        return session['language']
    
    # Otherwise detect from browser or IP
    # Get browser's preferred languages
    browser_languages = request.accept_languages.values()
    
    # Check if any of our supported languages match the browser languages
    for lang in browser_languages:
        if lang[:2] == 'pt':  # For Brazilian Portuguese
            return 'pt_BR'
        if lang[:2] in LANGUAGES:
            return lang[:2]
            
    # Default to English if no match
    return DEFAULT_LANGUAGE

def configure_babel(app):
    """Configure Flask-Babel with the Flask application."""
    babel.init_app(app, locale_selector=get_locale)
    
    # Make languages available to all templates
    @app.context_processor
    def inject_languages():
        return dict(languages=LANGUAGES, current_language=get_locale())
    
    # Route to change language
    @app.route('/language/<language>')
    def set_language(language):
        # Validate that the language is supported
        if language in LANGUAGES:
            session['language'] = language
        
        # Redirect back to the page they were on
        return redirect(request.referrer or '/')
