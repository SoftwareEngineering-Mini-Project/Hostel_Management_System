from django.urls import path

from . import views

app_name = "allocations"

urlpatterns = [
    path("<int:pk>/", views.allocation_detail, name="detail"),
    path("<int:pk>/checkin/", views.allocation_check_in, name="checkin"),
    path("<int:pk>/checkout/", views.allocation_check_out, name="checkout"),
]
