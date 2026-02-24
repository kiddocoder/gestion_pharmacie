"""
Core — Audit Service

Provides methods for writing audit log entries from any app.

@file core/services.py
"""

import logging
from decimal import Decimal
from typing import Any

from django.forms.models import model_to_dict

from core.models import AuditLog

logger = logging.getLogger('pharmatrack')


class AuditService:
    """Centralised audit logging for every write operation."""

    @staticmethod
    def log(
        *,
        actor,
        action: str,
        model_name: str,
        object_id: str,
        old_values: dict[str, Any] | None = None,
        new_values: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str = '',
    ) -> AuditLog:
        return AuditLog.objects.create(
            actor=actor,
            action=action,
            model_name=model_name,
            object_id=str(object_id),
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    @staticmethod
    def snapshot(instance, fields=None) -> dict[str, Any]:
        """
        Serialise a model instance to a plain dict suitable for JSONB
        storage. DateTimes are ISO-formatted; UUIDs stringified;
        M2M / querysets reduced to lists of PKs.
        """
        data = model_to_dict(instance, fields=fields)
        cleaned: dict[str, Any] = {}
        for key, value in data.items():
            if value is None:
                cleaned[key] = None
            elif isinstance(value, Decimal):
                cleaned[key] = str(value)
            elif hasattr(value, 'isoformat'):
                cleaned[key] = value.isoformat()
            elif hasattr(value, 'hex'):
                cleaned[key] = str(value)
            elif hasattr(value, 'all'):
                cleaned[key] = [str(obj.pk) for obj in value.all()]
            elif isinstance(value, (list, tuple)):
                cleaned[key] = [str(v.pk) if hasattr(v, 'pk') else v for v in value]
            else:
                cleaned[key] = value
        return cleaned

    @staticmethod
    def get_client_ip(request) -> str | None:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
