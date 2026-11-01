from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def is_admin(user):
    """Return True if the user is authenticated and is an administrator (staff member)."""
    return bool(user and user.is_authenticated and user.is_staff)


def is_student(user):
    """Return True if the user is authenticated and is a student (non-staff user)."""
    return bool(user and user.is_authenticated and not user.is_staff)


def admin_required(view_func):
    """Only logged-in staff (Hostel Administrators) may use the view.

    Anonymous users are sent to the login page; logged-in students get HTTP 403 (SAD 2.4, SRS SR-001..SR-005).
    """

    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.is_staff:
            raise PermissionDenied("Administrator access required.")
        return view_func(request, *args, **kwargs)

    return wrapped


def student_required(view_func):
    """Only logged-in students (non-staff users) may use the view.

    Anonymous users are sent to the login page; logged-in staff get HTTP 403 (HMS-F-002, SAD 2.4).
    """

    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if request.user.is_staff:
            raise PermissionDenied("Student access required.")
        return view_func(request, *args, **kwargs)

    return wrapped
