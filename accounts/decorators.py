from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def admin_required(view_func):
    """Only logged-in staff (Hostel Administrators) may use the view.

    Anonymous users are sent to the login page; logged-in students get HTTP 403 (SAD 2.4, SRS SR-001..SR-005).
    """

    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.is_staff:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapped
