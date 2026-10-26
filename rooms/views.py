from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import admin_required
from hostels.models import Hostel

from .forms import RoomForm
from .models import Room


@login_required
def room_list(request):
    """HMS-F-009: view rooms, filtered by hostel, floor, or availability status."""
    rooms = Room.objects.with_active_counts().select_related("hostel")

    hostel_id = request.GET.get("hostel", "")
    floor = request.GET.get("floor", "")
    status = request.GET.get("status", "")

    if hostel_id.isdigit():
        rooms = rooms.filter(hostel_id=int(hostel_id))
    try:
        rooms = rooms.filter(floor=int(floor))
    except ValueError:
        pass

    if status == "available":
        rooms = rooms.filter(active_count__lt=F("capacity"))
    elif status == "partial":
        rooms = rooms.filter(active_count__gt=0, active_count__lt=F("capacity"))
    elif status == "full":
        rooms = rooms.filter(active_count__gte=F("capacity"))

    return render(
        request,
        "rooms/room_list.html",
        {
            "rooms": rooms,
            "hostels": Hostel.objects.all(),
            "selected": {"hostel": hostel_id, "floor": floor, "status": status},
        },
    )


@login_required
def room_detail(request, pk):
    room = get_object_or_404(Room.objects.select_related("hostel"), pk=pk)
    return render(request, "rooms/room_detail.html", {"room": room})


@admin_required
def room_create(request):
    form = RoomForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        room = form.save()
        messages.success(request, f"Room {room.room_number} was added.")
        return redirect("rooms:detail", pk=room.pk)
    return render(
        request,
        "generic_form.html",
        {"form": form, "title": "Add room", "cancel_url": "/rooms/"},
    )


@admin_required
def room_update(request, pk):
    room = get_object_or_404(Room, pk=pk)
    form = RoomForm(request.POST or None, instance=room)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Room {room.room_number} was updated.")
        return redirect("rooms:detail", pk=room.pk)
    return render(
        request,
        "generic_form.html",
        {"form": form, "title": f"Edit room {room.room_number}", "cancel_url": f"/rooms/{room.pk}/"},
    )
