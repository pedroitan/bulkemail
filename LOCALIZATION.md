# Internationalization (i18n) for Bulk Email Scheduler

This document explains how the internationalization system works in the Bulk Email Scheduler application, with a focus on Brazilian Portuguese support.

## Overview

The application uses Flask-Babel for internationalization. This allows the interface to be presented in different languages based on:

1. User's browser language settings
2. User's manual language selection
3. Geographic location (when applicable)

Currently supported languages:
- English (default)
- Brazilian Portuguese (pt_BR)

## How Internationalization Works

### Technology Stack

- **Flask-Babel**: Core library for translations
- **Jinja2 Templates**: Uses the `{{ _('text') }}` syntax for translatable strings
- **Python Code**: Uses `gettext('text')` for translatable strings

### Files and Directories

- `translations.py`: Central module that handles language detection and selection
- `babel.cfg`: Configuration file for the Babel extraction tool
- `translations/`: Directory containing all translation files
  - `pt_BR/LC_MESSAGES/messages.po`: Brazilian Portuguese translation source
  - `pt_BR/LC_MESSAGES/messages.mo`: Compiled translation (binary)
- `extract_translations.py`: Script to extract translatable strings
- `compile_translations.py`: Script to compile translations into binary files

### Language Selection

The application provides a language dropdown in the navigation bar. When a user selects a language:

1. The selection is stored in the user's session
2. The UI immediately updates to the selected language
3. The preference persists across sessions

## Maintaining Translations

### Adding New Strings for Translation

1. In Python code, wrap strings with `gettext()`:
   ```python
   from flask_babel import gettext
   message = gettext("This is a translatable message")
   ```

2. In Jinja2 templates, use the `{{ _('text') }}` syntax:
   ```html
   <h1>{{ _('Welcome to the Application') }}</h1>
   ```

### Updating Translations

When you add new translatable strings to the application:

1. Run the extraction script to update the message catalog:
   ```
   python extract_translations.py
   ```

2. Edit the `translations/pt_BR/LC_MESSAGES/messages.po` file to add translations for the new strings

3. Compile the translations:
   ```
   python compile_translations.py
   ```

4. Restart the application to see the changes

## Adding More Languages

To add support for additional languages:

1. Update the `LANGUAGES` dictionary in `translations.py`
2. Run the extraction tool with the new language code:
   ```
   pybabel init -i messages.pot -d translations -l [language_code]
   ```
3. Translate the strings in the new `.po` file
4. Compile the translations and restart the application

## Best Practices

1. **Use Context**: Add comments in the `.po` files to provide context for translators
2. **Test with Different Languages**: Regularly test the application with all supported languages
3. **Keep Translations Updated**: Update translations whenever you add new UI elements
4. **Use Variables Carefully**: Remember that sentence structure varies between languages

## Integration with Render Deployment

When deploying to Render, note that our application is optimized to work within the limitations of Render's free tier. The internationalization system has been designed to:

1. Compile translations during the build phase
2. Use minimal memory for translation lookups
3. Work with the synchronous processing approach implemented for email campaigns

The internationalization system does not interfere with the existing optimizations for processing email campaigns synchronously or the session management improvements for handling large campaigns.
