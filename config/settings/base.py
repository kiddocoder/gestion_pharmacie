"""
PharmaTrack-BI — Base Settings

Shared settings for all environments. Environment-specific overrides
live in development.py and production.py.

@file config/settings/base.py
"""

import os
from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
)

env_file = BASE_DIR / '.env'
if env_file.exists():
    environ.Env.read_env(str(env_file))

SECRET_KEY = env('SECRET_KEY', default='insecure-dev-key-change-in-production')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env('ALLOWED_HOSTS')


# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.postgres',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'django_filters',
    'corsheaders',
    'django_celery_beat',
]

LOCAL_APPS = [
    'core.apps.CoreConfig',
    'users.apps.UsersConfig',
    'geography.apps.GeographyConfig',
    'medicines.apps.MedicinesConfig',
    'pharmacies.apps.PharmaciesConfig',
    'stock.apps.StockConfig',
    'b2b.apps.B2bConfig',
    'public_sector.apps.PublicSectorConfig',
    'finance.apps.FinanceConfig',
    'inspection.apps.InspectionConfig',
    'analytics.apps.AnalyticsConfig',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'


# ---------------------------------------------------------------------------
# Database — PostgreSQL (overridden per environment)
# ---------------------------------------------------------------------------

DATABASES = {
    'default': env.db('DATABASE_URL', default='postgres://pharmatrack:pharmatrack@localhost:5432/pharmatrack_bi'),
}

if DATABASES['default']['ENGINE'] == 'django.db.backends.postgresql':
    DATABASES['default'].setdefault('OPTIONS', {})
    DATABASES['default']['OPTIONS']['options'] = '-c search_path=public'


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

AUTH_USER_MODEL = 'users.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 10}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------

LANGUAGE_CODE = 'fr'
TIME_ZONE = 'Africa/Bujumbura'
USE_I18N = True
USE_TZ = True

LANGUAGES = [
    ('fr', 'Français'),
    ('en', 'English'),
]


# ---------------------------------------------------------------------------
# Static & Media files
# ---------------------------------------------------------------------------

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'core.pagination.StandardPagination',
    'DEFAULT_RENDERER_CLASSES': (
        'core.renderers.StandardJSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ),
    'EXCEPTION_HANDLER': 'core.exceptions.standard_exception_handler',
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '60/minute',
        'user': '200/minute',
    },
    'DEFAULT_SCHEMA_CLASS': 'rest_framework.schemas.openapi.AutoSchema',
    'COERCE_DECIMAL_TO_STRING': False,
}


# ---------------------------------------------------------------------------
# SimpleJWT
# ---------------------------------------------------------------------------

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(
        minutes=env.int('JWT_ACCESS_TOKEN_LIFETIME_MINUTES', default=30)
    ),
    'REFRESH_TOKEN_LIFETIME': timedelta(
        days=env.int('JWT_REFRESH_TOKEN_LIFETIME_DAYS', default=7)
    ),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'TOKEN_OBTAIN_SERIALIZER': 'users.serializers.CustomTokenObtainPairSerializer',
}


# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------

CELERY_BROKER_URL = env('CELERY_BROKER_URL', default='redis://localhost:6379/1')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default='redis://localhost:6379/2')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'


# ---------------------------------------------------------------------------
# Redis / Cache
# ---------------------------------------------------------------------------

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': env('REDIS_URL', default='redis://localhost:6379/0'),
    }
}


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=['http://localhost:3000'])
CORS_ALLOW_CREDENTIALS = True


# ---------------------------------------------------------------------------
# Security defaults (overridden in production.py)
# ---------------------------------------------------------------------------

SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True


# ---------------------------------------------------------------------------
# Application-specific settings
# ---------------------------------------------------------------------------

OTP_EXPIRY_MINUTES = env.int('OTP_EXPIRY_MINUTES', default=5)
DEVICE_TOKEN_EXPIRY_DAYS = env.int('DEVICE_TOKEN_EXPIRY_DAYS', default=30)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'pharmatrack': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
