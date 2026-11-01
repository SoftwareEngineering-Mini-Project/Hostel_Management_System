from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path


def home(request):
    if not request.user.is_authenticated:
        return redirect("login")
    return redirect("dashboard:summary" if request.user.is_staff else "rooms:list")


urlpatterns = [
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("hostels/", include("hostels.urls")),
    path("rooms/", include("rooms.urls")),
    path("dashboard/", include("dashboard.urls")),
    path("", include("students.urls")),
]
