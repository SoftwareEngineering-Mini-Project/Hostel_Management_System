"""Authentication and user management services (SAD 2.5, HMS-F-001, HMS-F-002)."""

from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ValidationError


def authenticate_user(request, username, password):
    """Authenticate credentials and return the User instance if valid and active.

    HMS-F-001 / TC-AUTH-01:
    - Returns active User object on valid credentials.
    - Returns None if credentials do not match or user is inactive.
    """
    if not username or not password:
        return None
    user = authenticate(request, username=username, password=password)
    if user is not None and user.is_active:
        return user
    return None


def login_user(request, user):
    """Log in an authenticated user into the current session and cycle the session key.

    HMS-F-001, HMS-SR-005.
    """
    login(request, user)


def logout_user(request):
    """Log out the current user and flush session data to prevent session fixation.

    HMS-SR-005 / TC-SEC-05 / IT_AUTH_04.
    """
    logout(request)
    if hasattr(request, "session"):
        request.session.flush()


def get_redirect_url_for_user(user, next_url=None):
    """Determine the post-login landing URL based on user role.

    - Next URL is honored if safe and present.
    - Administrators (is_staff=True) land on the administrative dashboard ('dashboard:summary').
    - Students (is_staff=False) land on room availability ('rooms:list').
    """
    from django.utils.http import url_has_allowed_host_and_scheme

    if next_url and url_has_allowed_host_and_scheme(
        url=next_url, allowed_hosts={""}, require_https=False
    ):
        return next_url

    if user.is_authenticated and user.is_staff:
        return "/dashboard/"
    return "/rooms/"
