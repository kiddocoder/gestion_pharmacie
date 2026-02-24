"""
PharmaTrack-BI — Development Settings

Local development overrides. Activated by:
  DJANGO_SETTINGS_MODULE=config.settings.development

@file config/settings/development.py
"""

from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ['*']

INSTALLED_APPS += [  # noqa: F405
    'django_extensions',
]

REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {  # noqa: F405
    'anon': '1000/minute',
    'user': '5000/minute',
}

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

LOGGING['loggers']['pharmatrack']['level'] = 'DEBUG'  # noqa: F405
