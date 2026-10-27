from django.urls import path

from . import views

app_name = "students"

# Included at the site root so the student's own page can live at /student/home/ (SAD 3.3.1).
urlpatterns = [
    path("students/", views.student_list, name="list"),
    path("students/new/", views.student_create, name="create"),
    path("students/<int:pk>/", views.student_detail, name="detail"),
    path("students/<int:pk>/edit/", views.student_update, name="update"),
    path("student/home/", views.my_profile, name="my_profile"),
]
