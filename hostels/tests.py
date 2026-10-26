"""SEM-41 (QA-RTM): hostel module tests. Each test name carries its test case ID (STP section 8)."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Hostel

User = get_user_model()


class HostelModuleTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin", password="admin-pass-123", is_staff=True)
        self.student = User.objects.create_user("stu1", password="student-pass-123")

    def valid_payload(self, **overrides):
        data = {
            "name": "Block A",
            "code": "BLA",
            "total_capacity": 40,
            "address": "North campus",
            "notes": "",
        }
        data.update(overrides)
        return data

    def test_TC_HOSTEL_01_admin_creates_views_and_updates_hostel(self):
        """HMS-F-006: a valid hostel can be created, viewed and updated."""
        self.client.force_login(self.admin)

        response = self.client.post(reverse("hostels:create"), self.valid_payload())
        self.assertEqual(response.status_code, 302)
        hostel = Hostel.objects.get(code="BLA")

        response = self.client.get(reverse("hostels:detail", args=[hostel.pk]))
        self.assertContains(response, "Block A")
        self.assertContains(response, "North campus")

        response = self.client.post(
            reverse("hostels:update", args=[hostel.pk]),
            self.valid_payload(name="Block A North", total_capacity=50),
        )
        self.assertEqual(response.status_code, 302)
        hostel.refresh_from_db()
        self.assertEqual(hostel.name, "Block A North")
        self.assertEqual(hostel.total_capacity, 50)

    def test_TC_HOSTEL_01_rejects_zero_capacity(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("hostels:create"), self.valid_payload(total_capacity=0))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Total capacity must be at least 1.")
        self.assertFalse(Hostel.objects.exists())

    def test_TC_HOSTEL_01_rejects_duplicate_code(self):
        Hostel.objects.create(name="Old", code="BLA", total_capacity=10)
        self.client.force_login(self.admin)
        response = self.client.post(reverse("hostels:create"), self.valid_payload())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A hostel with this code already exists.")
        self.assertEqual(Hostel.objects.count(), 1)

    def test_TC_HOSTEL_01_student_cannot_manage_hostels(self):
        """SR-001 / SR-005: students get 403 on admin hostel pages."""
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("hostels:list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("hostels:create")).status_code, 403)

    def test_TC_HOSTEL_01_anonymous_user_is_sent_to_login(self):
        response = self.client.get(reverse("hostels:list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])
