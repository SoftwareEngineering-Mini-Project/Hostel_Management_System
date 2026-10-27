from django.contrib import admin

from .models import Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ["srn", "name", "department", "year_of_study", "email"]
    search_fields = ["srn", "name"]
