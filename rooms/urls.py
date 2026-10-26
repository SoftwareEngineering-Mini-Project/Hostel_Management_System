from django.urls import path

from . import views

app_name = "rooms"

urlpatterns = [
    path("", views.room_list, name="list"),
    path("new/", views.room_create, name="create"),
    path("<int:pk>/", views.room_detail, name="detail"),
    path("<int:pk>/edit/", views.room_update, name="update"),
]
