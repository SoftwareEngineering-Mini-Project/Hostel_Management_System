from django.urls import path

from . import views

app_name = "hostels"

urlpatterns = [
    path("", views.hostel_list, name="list"),
    path("new/", views.hostel_create, name="create"),
    path("<int:pk>/", views.hostel_detail, name="detail"),
    path("<int:pk>/edit/", views.hostel_update, name="update"),
]
