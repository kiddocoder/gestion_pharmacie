"""
Geography — Models

Self-referencing AdministrativeLevel model representing Burundi's
post-2022 subdivision: Province → Commune → Zone → Colline/Quartier.

Parent-child integrity is enforced via CheckConstraint at the DB level.

@file geography/models.py
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import BaseModel


class AdministrativeLevel(BaseModel):
    """
    Hierarchical administrative division of Burundi.

    The post-2022 reform defines four levels:
      PROVINCE (18 total) → COMMUNE → ZONE → COLLINE

    Each level references its parent (except PROVINCE, whose parent is NULL).
    """

    class LevelType(models.TextChoices):
        PROVINCE = 'PROVINCE', _('Province')
        COMMUNE = 'COMMUNE', _('Commune')
        ZONE = 'ZONE', _('Zone')
        COLLINE = 'COLLINE', _('Colline / Quartier')

    PARENT_LEVEL_MAP = {
        'COMMUNE': 'PROVINCE',
        'ZONE': 'COMMUNE',
        'COLLINE': 'ZONE',
    }

    name = models.CharField(_('name'), max_length=150)
    code = models.CharField(_('code'), max_length=30, unique=True, db_index=True)
    level_type = models.CharField(
        _('level type'), max_length=10,
        choices=LevelType.choices, db_index=True,
    )
    parent = models.ForeignKey(
        'self',
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='children',
        verbose_name=_('parent'),
    )

    class Meta:
        verbose_name = _('administrative level')
        verbose_name_plural = _('administrative levels')
        ordering = ['level_type', 'name']
        indexes = [
            models.Index(fields=['level_type', 'parent']),
            models.Index(fields=['name']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(level_type='PROVINCE', parent__isnull=True)
                    | models.Q(level_type__in=['COMMUNE', 'ZONE', 'COLLINE'], parent__isnull=False)
                ),
                name='valid_parent_nullability',
            ),
        ]

    def __str__(self):
        return f'{self.name} ({self.get_level_type_display()})'

    @property
    def full_path(self) -> str:
        """Return the full hierarchy path, e.g. 'Province > Commune > Zone > Colline'."""
        parts = [self.name]
        current = self.parent
        while current:
            parts.insert(0, current.name)
            current = current.parent
        return ' > '.join(parts)

    def get_descendants(self, include_self=False):
        """Recursively collect all descendants."""
        result = [self] if include_self else []
        for child in self.children.all():
            result.append(child)
            result.extend(child.get_descendants())
        return result
