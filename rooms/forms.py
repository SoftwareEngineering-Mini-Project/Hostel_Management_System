from django import forms

from accounts.forms import BootstrapFormMixin

from .models import Room


class RoomForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Room
        fields = ["hostel", "room_number", "capacity", "floor"]
        error_messages = {
            "hostel": {"required": "Please choose a hostel for this room."},
            "room_number": {"required": "Please enter a room number."},
            "capacity": {"required": "Please enter the room capacity."},
        }
