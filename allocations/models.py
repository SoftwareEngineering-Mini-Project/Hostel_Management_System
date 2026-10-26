from django.conf import settings
from django.db import models


class Allocation(models.Model):
    """A student's use of a bed in a room.

    Only ACTIVE allocations occupy a bed (SAD glossary). Full allocation workflow
    (allocate_room, modify, cancel, history) belongs to HMS-F-010..F-014 and is not built here.
    """

    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    STATUS_CHOICES = [
        (ACTIVE, "Active"),
        (COMPLETED, "Completed"),
        (CANCELLED, "Cancelled"),
    ]

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="allocations"
    )
    room = models.ForeignKey("rooms.Room", on_delete=models.CASCADE, related_name="allocations")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student} in {self.room} ({self.status})"
