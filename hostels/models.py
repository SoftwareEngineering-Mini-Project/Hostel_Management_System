from django.db import models


class Hostel(models.Model):
    """HMS-F-006: a hostel block the administrator can create and maintain."""

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    total_capacity = models.PositiveIntegerField(default=0)
    address = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"
