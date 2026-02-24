"""
Users — Authentication Backend

Phone-based authentication backend for Django's auth system.

@file users/backends.py
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

User = get_user_model()


class PhoneBackend(ModelBackend):
    """Authenticate using phone + password instead of username."""

    def authenticate(self, request, phone=None, password=None, **kwargs):
        if phone is None:
            return None
        try:
            user = User.objects.get(phone=phone, is_deleted=False)
        except User.DoesNotExist:
            User().set_password(password)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
