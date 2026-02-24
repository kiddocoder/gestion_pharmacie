"""
Medicines — Celery Tasks

Periodic tasks for lot lifecycle automation.

@file medicines/tasks.py
"""

import logging

from celery import shared_task

logger = logging.getLogger('pharmatrack')


@shared_task(name='medicines.expire_overdue_lots')
def expire_overdue_lots_task():
    """
    Daily task: set EXPIRED status on all ACTIVE lots past their expiry date.
    Registered with Celery Beat to run once per day at midnight.
    """
    from .services import LotService

    count = LotService.expire_overdue_lots()
    logger.info('expire_overdue_lots_task completed: %d lots expired.', count)
    return {'expired_count': count}
