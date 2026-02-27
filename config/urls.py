"""
PharmaTrack-BI — Root URL Configuration

All API endpoints are namespaced under /api/v1/.
The DRF browsable API is available for route inspection in development.

@file config/urls.py
"""

from django.contrib import admin
from django.urls import include, path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.reverse import reverse

admin.site.site_header = 'PharmaTrack-BI Administration'
admin.site.site_title = 'PharmaTrack-BI'
admin.site.index_title = 'National Pharmaceutical Traceability Platform'


@api_view(['GET'])
@permission_classes([AllowAny])
def api_root(request, format=None):
    """PharmaTrack-BI API v1 — endpoint directory."""
    return Response({
        'auth': {
            'login': reverse('api-v1:auth:login', request=request, format=format),
            'refresh': reverse('api-v1:auth:token-refresh', request=request, format=format),
            'logout': reverse('api-v1:auth:logout', request=request, format=format),
            'otp_request': reverse('api-v1:auth:otp-request', request=request, format=format),
            'otp_verify': reverse('api-v1:auth:otp-verify', request=request, format=format),
            'me': reverse('api-v1:auth:me', request=request, format=format),
        },
        'users': reverse('api-v1:users:user-list', request=request, format=format),
        'geography': {
            'levels': reverse('api-v1:geography:level-list', request=request, format=format),
        },
        'medicines': {
            'list': reverse('api-v1:medicines:medicine-list', request=request, format=format),
            'lots': reverse('api-v1:medicines:lots:lot-list', request=request, format=format),
        },
        'pharmacies': reverse('api-v1:pharmacies:pharmacy-list', request=request, format=format),
        'b2b': {
            'orders': reverse('api-v1:b2b:order-list', request=request, format=format),
        },
    })


api_v1_patterns = [
    path('', api_root, name='api-root'),
    path('auth/', include('users.urls', namespace='auth')),
    path('users/', include('users.urls_users', namespace='users')),
    path('geography/', include('geography.urls', namespace='geography')),
    path('medicines/', include('medicines.urls', namespace='medicines')),
    path('pharmacies/', include('pharmacies.urls', namespace='pharmacies')),
    path('b2b/', include('b2b.urls', namespace='b2b')),
]

urlpatterns = [
    path('admin/', admin.site.urls),

    # DRF session auth (powers the "Log in" button on the browsable API)
    path('api/auth/', include('rest_framework.urls', namespace='rest_framework')),

    # Versioned API
    path('api/v1/', include((api_v1_patterns, 'api-v1'))),
]
