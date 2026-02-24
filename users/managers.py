"""
Users — Custom Managers

Custom UserManager enforcing email-based authentication with UUID PKs.

@file users/managers.py
"""

from django.contrib.auth.models import BaseUserManager
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    """Custom manager: create_user / create_superuser with email as identifier."""

    def _create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError(_('Phone number is required.'))
        user = self.model(phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, phone, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(phone, password, **extra_fields)

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('status', 'ACTIVE')

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self._create_user(phone, password, **extra_fields)

    def active(self):
        return self.filter(status='ACTIVE', is_deleted=False)
