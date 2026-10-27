from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import LoginForm
from .services import authenticate_user, get_redirect_url_for_user, login_user, logout_user


def login_view(request):
    """HMS-F-001 / TC-AUTH-01: User authentication for administrators and students.

    - Valid credentials redirect to role landing page or requested URL.
    - Invalid credentials return helpful feedback without revealing specific account state.
    """
    if request.user.is_authenticated:
        return redirect(get_redirect_url_for_user(request.user))

    redirect_to = request.POST.get("next") or request.GET.get("next", "")

    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login_user(request, user)
            target = redirect_to or get_redirect_url_for_user(user)
            return redirect(target)
    else:
        form = LoginForm(request)

    return render(
        request,
        "registration/login.html",
        {
            "form": form,
            "next": redirect_to,
        },
    )


def logout_view(request):
    """HMS-SR-005 / TC-SEC-05: Invalidate user session on logout and redirect to login."""
    logout_user(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect("login")
