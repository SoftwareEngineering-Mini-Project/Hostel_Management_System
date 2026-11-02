from django.conf import settings
from django.db import models


class Allocation(models.Model):
    """A student's use of a bed in a room.

    Only ACTIVE allocations occupy a bed (SAD glossary). Check-in / check-out (HMS-F-015, F-016) live in
    allocations/services.py; allocate_room, modify, cancel (HMS-F-010..F-014) are not built here yet.
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
    checked_in_on = models.DateTimeField(null=True, blank=True)
    checked_out_on = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.student} in {self.room} ({self.status})"

    def can_check_in(self):
        """SAD 3.1: check-in only on an ACTIVE allocation that is not already checked in."""
        return self.status == self.ACTIVE and self.checked_in_on is None

    def can_check_out(self):
        """SAD 3.1: check-out only on an ACTIVE allocation after check-in."""
        return self.status == self.ACTIVE and self.checked_in_on is not None


class AllocationHistory(models.Model):
    """HMS-F-018 / ADR-06: one row per change to an allocation, written only by allocations/services.py."""

    CREATED = "CREATED"
    MODIFIED = "MODIFIED"
    CANCELLED = "CANCELLED"
    CHECKED_IN = "CHECKED_IN"
    CHECKED_OUT = "CHECKED_OUT"
    ACTION_CHOICES = [
        (CREATED, "Created"),
        (MODIFIED, "Modified"),
        (CANCELLED, "Cancelled"),
        (CHECKED_IN, "Checked in"),
        (CHECKED_OUT, "Checked out"),
    ]

    allocation = models.ForeignKey(Allocation, on_delete=models.CASCADE, related_name="history")
    action = models.CharField(max_length=12, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp", "-id"]
        verbose_name_plural = "allocation history"

    def __str__(self):
        return f"{self.allocation_id} {self.action} by {self.performed_by}"
