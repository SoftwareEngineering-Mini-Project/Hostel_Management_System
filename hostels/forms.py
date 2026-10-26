from django import forms

from accounts.forms import BootstrapFormMixin

from .models import Hostel


class HostelForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Hostel
        fields = ["name", "code", "total_capacity", "address", "notes"]
        error_messages = {
            "name": {"required": "Please enter a hostel name."},
            "code": {
                "required": "Please enter a hostel code.",
                "unique": "A hostel with this code already exists.",
            },
            "total_capacity": {"required": "Please enter the total capacity."},
        }

    def clean_total_capacity(self):
        capacity = self.cleaned_data["total_capacity"]
        if capacity < 1:
            raise forms.ValidationError("Total capacity must be at least 1.")
        return capacity
