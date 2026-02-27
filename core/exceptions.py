"""
Core — Exception Handling

Custom exceptions and DRF exception handler for consistent API
error envelopes.

@file core/exceptions.py
"""

import logging

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger('pharmatrack')


# ---------------------------------------------------------------------------
# Domain exceptions
# ---------------------------------------------------------------------------

class BusinessRuleViolation(APIException):
    """Raised when a business rule is violated at the service layer."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Business rule violation.'
    default_code = 'BUSINESS_RULE_VIOLATION'


class InsufficientStockError(APIException):
    """Raised when an outbound stock movement exceeds available balance (e.g. concurrent sale)."""
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'Insufficient stock for this operation.'
    default_code = 'INSUFFICIENT_STOCK'


class InvalidStateTransition(BusinessRuleViolation):
    """Raised when a state machine transition is not allowed."""
    default_detail = 'Invalid state transition.'
    default_code = 'INVALID_STATE_TRANSITION'


class DuplicateResourceError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'Resource already exists.'
    default_code = 'DUPLICATE_RESOURCE'


class ResourceNotFoundError(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Resource not found.'
    default_code = 'RESOURCE_NOT_FOUND'


class AuthenticationFailedError(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = 'Authentication failed.'
    default_code = 'AUTHENTICATION_FAILED'


# ---------------------------------------------------------------------------
# Standard exception handler
# ---------------------------------------------------------------------------

def standard_exception_handler(exc, context):
    """
    Wraps every error response in the standard envelope:
      { "success": false, "errors": {...}, "code": "ERROR_CODE" }
    """
    if isinstance(exc, Http404):
        exc = ResourceNotFoundError()
    elif isinstance(exc, PermissionDenied):
        exc = APIException(detail='Permission denied.', code='PERMISSION_DENIED')
        exc.status_code = status.HTTP_403_FORBIDDEN
    elif isinstance(exc, ValidationError):
        data = {
            'success': False,
            'errors': exc.message_dict if hasattr(exc, 'message_dict') else {'detail': exc.messages},
            'code': 'VALIDATION_ERROR',
        }
        return Response(data, status=status.HTTP_400_BAD_REQUEST)

    response = exception_handler(exc, context)

    if response is not None:
        errors = {}
        code = getattr(exc, 'default_code', 'ERROR')

        if isinstance(response.data, dict):
            errors = response.data
            code = response.data.pop('code', code) if 'code' in response.data else code
        elif isinstance(response.data, list):
            errors = {'detail': response.data}
        else:
            errors = {'detail': [str(response.data)]}

        response.data = {
            'success': False,
            'errors': errors,
            'code': code,
        }

    if response is None:
        logger.exception('Unhandled exception in view: %s', exc)
        return Response(
            {'success': False, 'errors': {'detail': ['Internal server error.']}, 'code': 'INTERNAL_ERROR'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return response
