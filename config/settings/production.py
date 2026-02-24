"""
PharmaTrack-BI — Production Settings

Hardened configuration for deployment. Activated by:
  DJANGO_SETTINGS_MODULE=config.settings.production

@file config/settings/production.py
"""

from .base import *  # noqa: F401, F403

DEBUG = False

SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

DATABASES['default']['CONN_MAX_AGE'] = 600  # noqa: F405
DATABASES['default']['CONN_HEALTH_CHECKS'] = True  # noqa: F405

REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = (  # noqa: F405
    'core.renderers.StandardJSONRenderer',
)

LOGGING['loggers']['pharmatrack']['level'] = 'WARNING'  # noqa: F405
