from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models

phone_validator = RegexValidator(r"^\d{10}$", message="Phone must be 10 digits.")


class Student(models.Model):
    """HMS-F-003: a hostel student, linked one-to-one to the login user they sign in with."""

    MALE = "M"
    FEMALE = "F"
    OTHER = "O"
    GENDER_CHOICES = [(MALE, "Male"), (FEMALE, "Female"), (OTHER, "Other")]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="student"
    )
    srn = models.CharField("SRN", max_length=20, unique=True)
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=10, validators=[phone_validator])
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    department = models.CharField(max_length=50)
    year_of_study = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1, message="Year of study must be between 1 and 5."),
            MaxValueValidator(5, message="Year of study must be between 1 and 5."),
        ]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["srn"]

    def __str__(self):
        return f"{self.name} ({self.srn})"

    def current_allocation(self):
        """The student's ACTIVE allocation, or None. Read-only; allocation changes belong to allocations/."""
        from allocations.models import Allocation

        return (
            self.user.allocations.filter(status=Allocation.ACTIVE)
            .select_related("room__hostel")
            .first()
        )
