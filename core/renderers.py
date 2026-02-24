"""
Core — Response Renderer

Wraps all successful responses in the standard envelope:
  { "success": true, "data": ..., "meta": ... }

@file core/renderers.py
"""

from rest_framework.renderers import JSONRenderer


class StandardJSONRenderer(JSONRenderer):
    """Wraps successful API responses in a consistent envelope."""

    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = renderer_context.get('response') if renderer_context else None

        if response is not None and response.status_code >= 400:
            return super().render(data, accepted_media_type, renderer_context)

        if isinstance(data, dict) and 'success' in data:
            return super().render(data, accepted_media_type, renderer_context)

        if isinstance(data, dict) and 'results' in data:
            envelope = {
                'success': True,
                'data': data['results'],
                'meta': {
                    'count': data.get('count'),
                    'next': data.get('next'),
                    'previous': data.get('previous'),
                },
            }
        else:
            envelope = {
                'success': True,
                'data': data,
            }

        return super().render(envelope, accepted_media_type, renderer_context)
