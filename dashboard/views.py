from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.shortcuts import render

from accounts.decorators import admin_required
from allocations.models import Allocation
from hostels.models import Hostel
from rooms.models import Room


def build_summary():
    """HMS-F-019: summary metrics computed from stored records (read-only)."""
    room_totals = Room.objects.aggregate(total_rooms=Count("id"), total_capacity=Sum("capacity"))
    rooms = Room.objects.with_active_counts()
    available = sum(max(room.capacity - room.active_count, 0) for room in rooms)
    return {
        "students": get_user_model().objects.filter(is_staff=False, is_superuser=False).count(),
        "hostels": Hostel.objects.count(),
        "rooms": room_totals["total_rooms"] or 0,
        "total_capacity": room_totals["total_capacity"] or 0,
        "occupancy": Allocation.objects.filter(status=Allocation.ACTIVE).count(),
        "available": available,
    }


@admin_required
def summary(request):
    return render(request, "dashboard/summary.html", {"stats": build_summary()})
