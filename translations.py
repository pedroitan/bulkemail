"""
Internationalization support for the Bulk Email Scheduler.

This module provides language detection and translation functionality using Flask-Babel.
It detects the user's preferred language from browser headers and geolocation,
while also allowing manual language selection that's saved in the user's session.
"""

from flask import request, session, g, redirect
try:
    from flask_babel import Babel, gettext as _
except ImportError:
    # Fallback for older versions
    from flask.ext.babel import Babel, gettext as _

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
    """Configure Flask-Babel with the Flask application using a compatible approach."""
    # Initialize Babel with the most basic configuration
    try:
        # Try newer Flask-Babel API (locale_selector parameter)
        babel.init_app(app, locale_selector=get_locale)
    except TypeError:
        # Fall back to older Flask-Babel API (localeselector decorator)
        babel.init_app(app)
        try:
            @babel.localeselector
            def get_locale_for_babel():
                return get_locale()
        except AttributeError:
            # If neither approach works, just proceed without locale selection
            app.logger.warning("Flask-Babel locale selection could not be configured. Using default locale.")
    
    # Explicitly add translation functions to Jinja environment (works for all versions)
    app.jinja_env.globals.update({
        '_': _,
    })
    
    # Print the current translations path to help debug
    import os
    app.logger.info(f"Using translations from: {os.path.join(os.path.dirname(__file__), 'translations')}")
    app.logger.info(f"Available languages: {list(LANGUAGES.keys())}")
    app.logger.info(f"Default language: {DEFAULT_LANGUAGE}")
    
    # Language is automatically detected based on browser settings
    # You can uncomment the line below to force Portuguese for testing
    # babel.locale_selector_func = lambda: 'pt_BR'
    
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
