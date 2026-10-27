from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.decorators import admin_required

from .forms import StudentRegistrationForm, StudentUpdateForm
from .models import Student
from .services import get_student_for_user, register_student, search_students, update_student

PAGE_SIZE = 20


@admin_required
def student_list(request):
    """HMS-F-017: list and search students by SRN or name."""
    query = request.GET.get("q", "").strip()
    page = Paginator(search_students(query), PAGE_SIZE).get_page(request.GET.get("page"))
    return render(request, "students/student_list.html", {"page": page, "query": query})


@admin_required
def student_create(request):
    """HMS-F-003: register a student and their login account."""
    form = StudentRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        details = {k: v for k, v in form.cleaned_data.items() if k not in ("password1", "password2")}
        student = register_student(password=form.cleaned_data["password1"], **details)
        messages.success(request, f"Student {student.name} was registered.")
        return redirect("students:list")
    return render(
        request,
        "generic_form.html",
        {"form": form, "title": "Register student", "cancel_url": reverse("students:list")},
    )


@admin_required
def student_detail(request, pk):
    student = get_object_or_404(Student.objects.select_related("user"), pk=pk)
    return render(
        request,
        "students/student_detail.html",
        {"student": student, "allocation": student.current_allocation()},
    )


@admin_required
def student_update(request, pk):
    """HMS-F-004: edit a student's details."""
    student = get_object_or_404(Student.objects.select_related("user"), pk=pk)
    form = StudentUpdateForm(request.POST or None, instance=student)
    if request.method == "POST" and form.is_valid():
        update_student(student, **form.cleaned_data)
        messages.success(request, f"Student {student.name} was updated.")
        return redirect("students:detail", pk=student.pk)
    return render(
        request,
        "generic_form.html",
        {
            "form": form,
            "title": f"Edit {student.name} ({student.srn})",
            "cancel_url": reverse("students:detail", args=[student.pk]),
        },
    )


@login_required
def my_profile(request):
    """HMS-F-005 / HMS-SR-006: a student sees only their own record, found from request.user."""
    student = get_student_for_user(request.user)
    allocation = student.current_allocation() if student else None
    return render(
        request,
        "students/my_profile.html",
        {"student": student, "allocation": allocation},
        status=200 if student else 404,
    )
