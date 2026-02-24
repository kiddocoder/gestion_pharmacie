"""
Medicines — Application Configuration
"""

from django.apps import AppConfig


class MedicinesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'medicines'
    verbose_name = 'National Medicine Registry'

    def ready(self):
        import medicines.signals  # noqa: F401
