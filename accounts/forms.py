from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .validators import sanitize_text, validate_no_script_tags


class SanitizedFormMixin:
    """Sanitizes text fields automatically across forms and blocks script injection (HMS-SR-004)."""

    def clean(self):
        cleaned_data = super().clean()
        for field_name, value in list(cleaned_data.items()):
            if isinstance(value, str):
                validate_no_script_tags(value)
                cleaned_data[field_name] = sanitize_text(value)
        return cleaned_data


class BootstrapFormMixin(SanitizedFormMixin):
    """Gives every field a consistent Bootstrap class and sanitizes text inputs (HMS-NF-004, HMS-SR-004)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", "form-select")
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-check-input")
            else:
                field.widget.attrs.setdefault("class", "form-control")


class LoginForm(BootstrapFormMixin, AuthenticationForm):
    """HMS-F-001: Standardized login form with bootstrap styling and clear error messages."""

    username = forms.CharField(
        label="Username",
        widget=forms.TextInput(
            attrs={"placeholder": "Enter username", "autofocus": True, "autocomplete": "username"}
        ),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={"placeholder": "Enter password", "autocomplete": "current-password"}
        ),
    )

    error_messages = {
        "invalid_login": "Invalid username or password.",
        "inactive": "This account is inactive.",
    }
