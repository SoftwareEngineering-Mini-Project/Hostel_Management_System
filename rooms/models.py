from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Count, Q

from allocations.models import Allocation


class RoomQuerySet(models.QuerySet):
    def with_active_counts(self):
        """Annotate each room with its ACTIVE allocation count in one SQL query (HMS-NF-001: avoids N+1)."""
        return self.annotate(
            active_count=Count("allocations", filter=Q(allocations__status=Allocation.ACTIVE))
        )


class Room(models.Model):
    """HMS-F-007: a room inside a hostel, with a capacity in beds. HMS-F-008: availability."""

    hostel = models.ForeignKey("hostels.Hostel", on_delete=models.CASCADE, related_name="rooms")
    room_number = models.CharField(max_length=20)
    capacity = models.PositiveIntegerField(
        validators=[MinValueValidator(1, message="Capacity must be at least 1.")]
    )
    floor = models.IntegerField(default=0)

    objects = RoomQuerySet.as_manager()

    class Meta:
        ordering = ["hostel__name", "floor", "room_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["hostel", "room_number"],
                name="unique_room_number_per_hostel",
                violation_error_message="This room number already exists in this hostel.",
            )
        ]

    def __str__(self):
        return f"{self.hostel.code}-{self.room_number}"

    def active_allocation_count(self):
        # Uses the annotation when the queryset provided it, otherwise queries once.
        if hasattr(self, "active_count"):
            return self.active_count
        return self.allocations.filter(status=Allocation.ACTIVE).count()

    def available_capacity(self):
        """available_capacity = capacity - count(active allocations), never below zero (SRS HMS-F-008)."""
        return max(self.capacity - self.active_allocation_count(), 0)

    def is_available(self):
        return self.available_capacity() > 0

    def availability_status(self):
        active = self.active_allocation_count()
        if active >= self.capacity:
            return "Full"
        if active > 0:
            return "Partially Occupied"
        return "Available"
