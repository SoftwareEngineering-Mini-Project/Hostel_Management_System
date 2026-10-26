"""SEM-44 (QA-RTM): dashboard, performance and usability tests. Test names carry the STP test case IDs."""

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from allocations.models import Allocation
from hostels.forms import HostelForm
from hostels.models import Hostel
from rooms.models import Room

User = get_user_model()


class DashboardTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin", password="admin-pass-123", is_staff=True)
        self.student = User.objects.create_user("stu1", password="student-pass-123")
        self.hostel = Hostel.objects.create(name="Block A", code="BLA", total_capacity=5)
        self.room1 = Room.objects.create(hostel=self.hostel, room_number="101", capacity=2)
        self.room2 = Room.objects.create(hostel=self.hostel, room_number="102", capacity=3)
        Allocation.objects.create(student=self.student, room=self.room1, status=Allocation.ACTIVE)
        Allocation.objects.create(student=self.student, room=self.room2, status=Allocation.CANCELLED)

    def test_TC_DASH_01_summary_matches_database_aggregates(self):
        """HMS-F-019: metrics match the stored records."""
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:summary"))
        stats = response.context["stats"]

        self.assertEqual(stats["students"], User.objects.filter(is_staff=False).count())
        self.assertEqual(stats["hostels"], Hostel.objects.count())
        self.assertEqual(stats["rooms"], Room.objects.count())
        self.assertEqual(stats["total_capacity"], 5)  # 2 + 3 from the rooms table
        self.assertEqual(stats["occupancy"], Allocation.objects.filter(status="ACTIVE").count())
        self.assertEqual(stats["occupancy"], 1)
        self.assertEqual(stats["available"], 4)  # (2-1) + (3-0)

    def test_TC_DASH_01_summary_updates_with_new_records(self):
        self.client.force_login(self.admin)
        Room.objects.create(hostel=self.hostel, room_number="103", capacity=4)
        stats = self.client.get(reverse("dashboard:summary")).context["stats"]
        self.assertEqual(stats["rooms"], 3)
        self.assertEqual(stats["total_capacity"], 9)

    def test_TC_DASH_01_student_cannot_view_admin_dashboard(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("dashboard:summary")).status_code, 403)


class PerformanceTests(TestCase):
    """HMS-NF-001 / TC-PERF-01: query count of the room list must not grow with the number of rooms."""

    def setUp(self):
        self.student = User.objects.create_user("stu1", password="student-pass-123")
        self.client.force_login(self.student)
        self.hostel = Hostel.objects.create(name="Block A", code="BLA", total_capacity=10)

    def add_rooms(self, count, start):
        for i in range(start, start + count):
            room = Room.objects.create(hostel=self.hostel, room_number=str(i), capacity=2)
            Allocation.objects.create(student=self.student, room=room, status=Allocation.ACTIVE)

    def count_queries_for_list(self):
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(reverse("rooms:list"))
        self.assertEqual(response.status_code, 200)
        return len(ctx.captured_queries)

    def test_TC_PERF_01_room_list_query_count_is_constant(self):
        self.add_rooms(3, start=100)
        small = self.count_queries_for_list()
        self.add_rooms(30, start=200)
        large = self.count_queries_for_list()
        self.assertEqual(small, large, "room list issues extra queries per room (N+1)")
        self.assertLessEqual(large, 8)

    def test_TC_PERF_01_room_list_responds_within_target(self):
        """Academic-load smoke check: a list page of 50 rooms renders well under 3 seconds."""
        import time

        self.add_rooms(50, start=300)
        start = time.perf_counter()
        self.client.get(reverse("rooms:list"))
        self.assertLess(time.perf_counter() - start, 3.0)


class UsabilityTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin", password="admin-pass-123", is_staff=True)
        self.student = User.objects.create_user("stu1", password="student-pass-123")

    def test_TC_UX_01_validation_messages_render_on_form(self):
        """HMS-NF-004: field-level validation messages are shown to the user."""
        self.client.force_login(self.admin)
        response = self.client.post(reverse("hostels:create"), {"name": "", "code": "X", "total_capacity": 5})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please enter a hostel name.")
        self.assertContains(response, 'class="invalid-feedback d-block"')

    def test_TC_UX_01_form_fields_use_standard_bootstrap_styling(self):
        form = HostelForm()
        for field in form.fields.values():
            self.assertIn("form-control", field.widget.attrs.get("class", ""))

    def test_TC_UX_01_admin_navigation_separated_from_student_navigation(self):
        self.client.force_login(self.admin)
        admin_page = self.client.get(reverse("home"), follow=True).content.decode()
        self.assertIn(reverse("hostels:list"), admin_page)
        self.assertIn("Administrator", admin_page)

        self.client.force_login(self.student)
        student_page = self.client.get(reverse("rooms:list")).content.decode()
        self.assertNotIn(reverse("hostels:list"), student_page)
        self.assertIn("Student", student_page)
