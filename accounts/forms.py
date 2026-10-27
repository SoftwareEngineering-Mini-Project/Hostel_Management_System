from django import forms
from django.contrib.auth.forms import AuthenticationForm


class BootstrapFormMixin:
    """Gives every field a consistent Bootstrap class (HMS-NF-004: standardized form styling)."""

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
