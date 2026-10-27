from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from accounts.forms import BootstrapFormMixin

from .models import Student

ERROR_MESSAGES = {
    "srn": {
        "required": "Please enter the SRN.",
        "unique": "Student with this SRN already exists.",
    },
    "name": {"required": "Please enter the student's name."},
    "email": {
        "required": "Please enter an email address.",
        "invalid": "Enter a valid email address.",
    },
    "phone": {"required": "Please enter a phone number."},
    "gender": {"required": "Please select a gender."},
    "department": {"required": "Please enter the department."},
    "year_of_study": {
        "required": "Please enter the year of study.",
        "invalid": "Year of study must be a whole number.",
    },
}

DETAIL_FIELDS = ["name", "email", "phone", "gender", "department", "year_of_study"]


class StudentRegistrationForm(BootstrapFormMixin, forms.ModelForm):
    """HMS-F-003: the administrator registers a student and sets their first password.

    The student's login username is their SRN.
    """

    # min_length is a floor of our own; Django's validators also run once settings define them (SEM-13).
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput,
        strip=False,
        min_length=8,
        error_messages={"min_length": "Password must be at least 8 characters."},
    )
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput, strip=False)

    class Meta:
        model = Student
        fields = ["srn", *DETAIL_FIELDS]
        error_messages = ERROR_MESSAGES

    def clean_srn(self):
        srn = self.cleaned_data["srn"].strip().upper()
        if Student.objects.filter(srn__iexact=srn).exists():
            raise forms.ValidationError("Student with this SRN already exists.")
        if get_user_model().objects.filter(username__iexact=srn).exists():
            raise forms.ValidationError("A login account with this SRN already exists.")
        return srn

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "The two passwords do not match.")
        elif p1:
            try:
                validate_password(p1)
            except forms.ValidationError as error:
                self.add_error("password1", error)
        return cleaned


class StudentUpdateForm(BootstrapFormMixin, forms.ModelForm):
    """HMS-F-004: edit a student's details. The SRN is the login name, so it is not editable here."""

    class Meta:
        model = Student
        fields = DETAIL_FIELDS
        error_messages = ERROR_MESSAGES
