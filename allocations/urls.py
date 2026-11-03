from django.urls import path

from . import views

app_name = "allocations"

# "new/" and "history/" come before "<int:pk>/" so they are never read as an id.
urlpatterns = [
    path("", views.allocation_list, name="list"),
    path("new/", views.allocation_create, name="create"),
    path("history/", views.allocation_history, name="history"),
    path("<int:pk>/", views.allocation_detail, name="detail"),
    path("<int:pk>/modify/", views.allocation_modify, name="modify"),
    path("<int:pk>/cancel/", views.allocation_cancel, name="cancel"),
    path("<int:pk>/checkin/", views.allocation_check_in, name="checkin"),
    path("<int:pk>/checkout/", views.allocation_check_out, name="checkout"),
]
