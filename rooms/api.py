from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from .models import Room


@login_required
@require_GET
def room_availability(request, room_id):
    """HMS-F-008 (SAD 3.3.3): GET /api/rooms/<room_id>/availability/ for admins and students.

    Availability is computed from ACTIVE allocations on every call, never stored (SAD 3.1).
    """
    room = get_object_or_404(Room.objects.select_related("hostel").with_active_counts(), pk=room_id)
    return JsonResponse(
        {
            "room_id": room.pk,
            "hostel": room.hostel.name,
            "room_number": room.room_number,
            "capacity": room.capacity,
            "active_allocations": room.active_allocation_count(),
            "available": room.available_capacity(),
        }
    )
