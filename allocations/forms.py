from django import forms
from django.contrib.auth import get_user_model

from rooms.models import Room

from .models import Allocation


class _StudentChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, user):
        profile = getattr(user, "student", None)
        return f"{profile.name} ({profile.srn})" if profile else user.get_username()


class _RoomChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, room):
        return f"{room.hostel.name}, room {room.room_number} ({room.available_capacity()} free)"


class AllocationForm(forms.Form):
    """HMS-F-010: pick a student and a room.

    The drop-downs only offer students without an ACTIVE allocation and rooms with a free bed, but any existing
    student/room is accepted on submit so the service layer gives the real error (SAD 3.4) if things changed.
    """

    student = _StudentChoiceField(queryset=get_user_model().objects.none())
    room = _RoomChoiceField(queryset=Room.objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        users = get_user_model().objects.filter(student__isnull=False, is_staff=False).select_related("student")
        rooms = Room.objects.select_related("hostel")
        self.fields["student"].queryset = users
        self.fields["room"].queryset = rooms
        offered_students = users.exclude(allocations__status=Allocation.ACTIVE).order_by("student__srn")
        offered_rooms = [r for r in rooms.with_active_counts() if r.available_capacity() > 0]
        self.fields["student"].widget.choices = [("", "---------")] + [
            (u.pk, self.fields["student"].label_from_instance(u)) for u in offered_students
        ]
        self.fields["room"].widget.choices = [("", "---------")] + [
            (r.pk, self.fields["room"].label_from_instance(r)) for r in offered_rooms
        ]
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select"
