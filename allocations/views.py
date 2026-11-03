from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.decorators import admin_required
from rooms.models import Room

from .forms import AllocationForm
from .models import Allocation, AllocationHistory
from .services import (
    AlreadyAllocatedError,
    InvalidStateError,
    RoomFullError,
    allocate_room,
    cancel_allocation,
    check_in,
    check_out,
    modify_allocation,
)

PAGE_SIZE = 25


def _get_allocation(pk):
    return get_object_or_404(Allocation.objects.select_related("student", "room__hostel"), pk=pk)


@admin_required
def allocation_list(request):
    """HMS-F-012: list allocations with student, room and status."""
    allocations = Allocation.objects.select_related("student", "room__hostel").order_by("-created_at", "-id")
    page = Paginator(allocations, PAGE_SIZE).get_page(request.GET.get("page"))
    return render(request, "allocations/allocation_list.html", {"page": page})


@admin_required
def allocation_create(request):
    """HMS-F-010 / F-011: allocate a room. A business error re-renders the form (200) and saves nothing."""
    form = AllocationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            allocate_room(form.cleaned_data["student"], form.cleaned_data["room"], request.user)
        except (RoomFullError, AlreadyAllocatedError) as error:
            form.add_error(None, str(error))
        else:
            messages.success(request, "Room allocated successfully")
            return redirect("allocations:list")
    return render(
        request,
        "generic_form.html",
        {"form": form, "title": "Allocate room", "cancel_url": reverse("allocations:list")},
    )


@admin_required
def allocation_detail(request, pk):
    """SAD 3.5: status and dates, with Check-in / Check-out / Modify / Cancel enabled only when allowed."""
    allocation = _get_allocation(pk)
    free_rooms = (
        Room.objects.select_related("hostel")
        .with_active_counts()
        .filter(active_count__lt=F("capacity"))
        .exclude(pk=allocation.room_id)
    )
    return render(
        request,
        "allocations/allocation_detail.html",
        {
            "allocation": allocation,
            "student": getattr(allocation.student, "student", None),
            "history": allocation.history.select_related("performed_by", "old_room__hostel", "new_room__hostel"),
            "free_rooms": free_rooms,
        },
    )


@admin_required
@require_POST
def allocation_modify(request, pk):
    """HMS-F-013: POST /allocations/<id>/modify/ with new_room moves the student to another room."""
    allocation = _get_allocation(pk)
    room_id = request.POST.get("new_room", "")
    new_room = Room.objects.filter(pk=int(room_id)).first() if room_id.isdigit() else None
    if new_room is None:
        messages.error(request, "Select a room to move the student to")
        return redirect("allocations:detail", pk=allocation.pk)
    try:
        modify_allocation(allocation, new_room, request.user)
    except (InvalidStateError, RoomFullError) as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Allocation updated successfully")
    return redirect("allocations:detail", pk=allocation.pk)


@admin_required
def allocation_cancel(request, pk):
    """HMS-F-014: GET shows a confirmation step, POST /allocations/<id>/cancel/ cancels."""
    allocation = _get_allocation(pk)
    if request.method != "POST":
        return render(request, "allocations/cancel_confirm.html", {"allocation": allocation})
    try:
        cancel_allocation(allocation, request.user)
    except InvalidStateError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Allocation cancelled")
    return redirect("allocations:detail", pk=allocation.pk)


@admin_required
def allocation_history(request):
    """HMS-F-018: the allocation history log, filterable by ?student=<user id> and ?room=<room id>."""
    entries = AllocationHistory.objects.select_related(
        "allocation__student", "allocation__room__hostel", "performed_by", "old_room__hostel", "new_room__hostel"
    )
    student_id = request.GET.get("student", "")
    room_id = request.GET.get("room", "")
    if student_id.isdigit():
        entries = entries.filter(allocation__student_id=int(student_id))
    if room_id.isdigit():
        room = int(room_id)
        entries = entries.filter(
            Q(new_room_id=room) | Q(old_room_id=room) | Q(old_room__isnull=True, new_room__isnull=True, allocation__room_id=room)
        )
    page = Paginator(entries, PAGE_SIZE).get_page(request.GET.get("page"))
    return render(
        request,
        "allocations/allocation_history.html",
        {"page": page, "student_id": student_id, "room_id": room_id},
    )


@admin_required
@require_POST
def allocation_check_in(request, pk):
    """HMS-F-015: POST /allocations/<id>/checkin/."""
    allocation = _get_allocation(pk)
    try:
        check_in(allocation, request.user)
    except InvalidStateError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Student checked in")
    return redirect("allocations:detail", pk=allocation.pk)


@admin_required
def allocation_check_out(request, pk):
    """HMS-F-016: GET shows a confirmation step (SAD 3.5), POST /allocations/<id>/checkout/ checks out."""
    allocation = _get_allocation(pk)
    if request.method != "POST":
        return render(request, "allocations/checkout_confirm.html", {"allocation": allocation})
    try:
        check_out(allocation, request.user)
    except InvalidStateError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Student checked out")
    return redirect("allocations:detail", pk=allocation.pk)
