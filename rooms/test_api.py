"""SEM-47: room availability JSON endpoint (HMS-F-008, TC-ROOM-02: IT_AVL_01, ST_AVL_01)."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from allocations.models import Allocation
from hostels.models import Hostel
from rooms.models import Room

User = get_user_model()


class RoomAvailabilityApiTests(TestCase):
    def setUp(self):
        self.stu1 = User.objects.create_user("stu1", password="student-pass-123")
        self.stu2 = User.objects.create_user("stu2", password="student-pass-123")
        self.stu3 = User.objects.create_user("stu3", password="student-pass-123")
        self.admin = User.objects.create_user("admin1", password="admin-pass-123", is_staff=True)
        hostel = Hostel.objects.create(name="Block A", code="BLA", total_capacity=20)
        self.room = Room.objects.create(hostel=hostel, room_number="A-101", capacity=3)
        Allocation.objects.create(student=self.stu1, room=self.room)
        Allocation.objects.create(student=self.stu2, room=self.room)
        # Cancelled and completed allocations must not count (UT_AVL_03).
        Allocation.objects.create(student=self.stu3, room=self.room, status=Allocation.CANCELLED)
        self.url = reverse("api_room_availability", args=[self.room.pk])

    def test_TC_ROOM_02_IT_AVL_01_returns_correct_values_for_student(self):
        self.client.force_login(self.stu1)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "room_id": self.room.pk,
                "hostel": "Block A",
                "room_number": "A-101",
                "capacity": 3,
                "active_allocations": 2,
                "available": 1,
            },
        )

    def test_TC_ROOM_02_admin_can_read_availability(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url).json()["available"], 1)

    def test_TC_ROOM_02_ST_AVL_01_value_updates_after_allocation(self):
        self.client.force_login(self.stu1)
        self.assertEqual(self.client.get(self.url).json()["available"], 1)
        Allocation.objects.filter(student=self.stu3).update(status=Allocation.ACTIVE)
        self.assertEqual(self.client.get(self.url).json()["available"], 0)

    def test_TC_ROOM_02_anonymous_is_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_TC_ROOM_02_unknown_room_returns_404(self):
        self.client.force_login(self.stu1)
        self.assertEqual(self.client.get(reverse("api_room_availability", args=[99999])).status_code, 404)

    def test_TC_ROOM_02_post_is_not_allowed(self):
        self.client.force_login(self.stu1)
        self.assertEqual(self.client.post(self.url).status_code, 405)
