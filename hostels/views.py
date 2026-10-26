from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import admin_required

from .forms import HostelForm
from .models import Hostel


@admin_required
def hostel_list(request):
    return render(request, "hostels/hostel_list.html", {"hostels": Hostel.objects.all()})


@admin_required
def hostel_detail(request, pk):
    hostel = get_object_or_404(Hostel, pk=pk)
    return render(
        request,
        "hostels/hostel_detail.html",
        {"hostel": hostel, "rooms": hostel.rooms.all()},
    )


@admin_required
def hostel_create(request):
    form = HostelForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        hostel = form.save()
        messages.success(request, f"Hostel {hostel.name} was created.")
        return redirect("hostels:detail", pk=hostel.pk)
    return render(
        request,
        "generic_form.html",
        {"form": form, "title": "Add hostel", "cancel_url": "/hostels/"},
    )


@admin_required
def hostel_update(request, pk):
    hostel = get_object_or_404(Hostel, pk=pk)
    form = HostelForm(request.POST or None, instance=hostel)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Hostel {hostel.name} was updated.")
        return redirect("hostels:detail", pk=hostel.pk)
    return render(
        request,
        "generic_form.html",
        {"form": form, "title": f"Edit {hostel.name}", "cancel_url": f"/hostels/{hostel.pk}/"},
    )
