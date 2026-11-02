from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import admin_required

from .models import Allocation
from .services import InvalidStateError, check_in, check_out


def _get_allocation(pk):
    return get_object_or_404(Allocation.objects.select_related("student", "room__hostel"), pk=pk)


@admin_required
def allocation_detail(request, pk):
    """SAD 3.5: status and dates, with Check-in / Check-out enabled only when allowed."""
    allocation = _get_allocation(pk)
    return render(
        request,
        "allocations/allocation_detail.html",
        {
            "allocation": allocation,
            "student": getattr(allocation.student, "student", None),
            "history": allocation.history.select_related("performed_by"),
        },
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
