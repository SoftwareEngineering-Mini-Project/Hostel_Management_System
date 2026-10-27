"""Student business logic (SAD 2.5: views call services, services call models)."""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q

from .models import Student


@transaction.atomic
def register_student(*, password, **details):
    """HMS-F-003: create the login user and the Student record together, or neither."""
    user = get_user_model().objects.create_user(
        username=details["srn"],
        email=details.get("email", ""),
        password=password,
        is_staff=False,
    )
    return Student.objects.create(user=user, **details)


def update_student(student, **details):
    """HMS-F-004: save changed details and keep the login email in step with the record."""
    for field, value in details.items():
        setattr(student, field, value)
    with transaction.atomic():
        student.save()
        if student.user.email != student.email:
            student.user.email = student.email
            student.user.save(update_fields=["email"])
    return student


def search_students(query):
    """HMS-F-017: case-insensitive match on any part of the SRN or name. An empty query returns everyone."""
    students = Student.objects.select_related("user")
    query = (query or "").strip()
    if query:
        students = students.filter(Q(srn__icontains=query) | Q(name__icontains=query))
    return students


def get_student_for_user(user):
    """HMS-SR-006: a student's own record is looked up from the logged-in user, never from a URL id."""
    return Student.objects.select_related("user").filter(user=user).first()
