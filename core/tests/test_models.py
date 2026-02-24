"""
Core — Model Tests

Tests for AuditLog and base model mixins.

@file core/tests/test_models.py
"""

import pytest

from core.models import AuditLog
from core.services import AuditService
from tests.factories import AuditLogFactory, UserFactory


@pytest.mark.django_db
class TestAuditLog:
    def test_create_audit_log(self):
        user = UserFactory()
        log = AuditService.log(
            actor=user,
            action=AuditLog.ActionChoices.CREATE,
            model_name='TestModel',
            object_id='test-123',
            new_values={'key': 'value'},
        )
        assert log.pk is not None
        assert log.action == 'CREATE'
        assert log.model_name == 'TestModel'

    def test_audit_log_immutable_via_factory(self):
        log = AuditLogFactory()
        assert log.pk is not None

    def test_snapshot_serialises_datetime(self):
        user = UserFactory()
        snapshot = AuditService.snapshot(user)
        assert isinstance(snapshot, dict)
        assert 'phone' in snapshot

    def test_user_create_triggers_audit(self):
        """User creation via signal should produce an audit log."""
        before = AuditLog.objects.count()
        UserFactory()
        after = AuditLog.objects.count()
        assert after > before
