"""
Core — Pagination

Standard paginator with configurable page_size and hard max cap.

@file core/pagination.py
"""

from rest_framework.pagination import PageNumberPagination

from core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE


class StandardPagination(PageNumberPagination):
    page_size = DEFAULT_PAGE_SIZE
    page_size_query_param = 'page_size'
    max_page_size = MAX_PAGE_SIZE
