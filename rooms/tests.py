"""SEM-41 (QA-RTM): room module tests. Each test name carries its test case ID (STP section 8)."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from allocations.models import Allocation
from hostels.models import Hostel

from .models import Room

User = get_user_model()


class RoomTestBase(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin", password="admin-pass-123", is_staff=True)
        self.student = User.objects.create_user("stu1", password="student-pass-123")
        self.hostel = Hostel.objects.create(name="Block A", code="BLA", total_capacity=20)
        self.other_hostel = Hostel.objects.create(name="Block B", code="BLB", total_capacity=10)

    def make_room(self, number="101", capacity=3, floor=1, hostel=None):
        return Room.objects.create(
            hostel=hostel or self.hostel, room_number=number, capacity=capacity, floor=floor
        )

    def allocate(self, room, status=Allocation.ACTIVE, username=None):
        student = User.objects.create_user(username or f"s{Allocation.objects.count()}-{room.pk}-{status}")
        return Allocation.objects.create(student=student, room=room, status=status)


class RoomInventoryTests(RoomTestBase):
    def test_TC_ROOM_01_admin_creates_and_updates_room(self):
        """HMS-F-007: a room with a valid hostel, number and capacity is saved and can be updated."""
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("rooms:create"),
            {"hostel": self.hostel.pk, "room_number": "201", "capacity": 2, "floor": 2},
        )
        self.assertEqual(response.status_code, 302)
        room = Room.objects.get(room_number="201")
        self.assertEqual(room.capacity, 2)

        response = self.client.post(
            reverse("rooms:update", args=[room.pk]),
            {"hostel": self.hostel.pk, "room_number": "201", "capacity": 4, "floor": 2},
        )
        self.assertEqual(response.status_code, 302)
        room.refresh_from_db()
        self.assertEqual(room.capacity, 4)

    def test_TC_ROOM_01_rejects_duplicate_room_number_in_same_hostel(self):
        """Boundary: duplicate room number within a hostel is rejected."""
        self.make_room(number="101")
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("rooms:create"),
            {"hostel": self.hostel.pk, "room_number": "101", "capacity": 2, "floor": 1},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This room number already exists in this hostel.")
        self.assertEqual(Room.objects.filter(room_number="101").count(), 1)

    def test_TC_ROOM_01_same_room_number_allowed_in_different_hostel(self):
        self.make_room(number="101", hostel=self.hostel)
        self.make_room(number="101", hostel=self.other_hostel)
        self.assertEqual(Room.objects.filter(room_number="101").count(), 2)

    def test_TC_ROOM_01_rejects_zero_capacity_boundary(self):
        """Boundary: capacity 0 is invalid, capacity 1 is the minimum valid value."""
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("rooms:create"),
            {"hostel": self.hostel.pk, "room_number": "301", "capacity": 0, "floor": 3},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Capacity must be at least 1.")

        response = self.client.post(
            reverse("rooms:create"),
            {"hostel": self.hostel.pk, "room_number": "301", "capacity": 1, "floor": 3},
        )
        self.assertEqual(response.status_code, 302)

    def test_TC_ROOM_01_student_cannot_create_rooms(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("rooms:create")).status_code, 403)


class RoomAvailabilityTests(RoomTestBase):
    def test_TC_ROOM_02_available_capacity_is_capacity_minus_active(self):
        """HMS-F-008: available_capacity = capacity - count(active allocations)."""
        room = self.make_room(capacity=3)
        self.allocate(room)
        self.assertEqual(room.available_capacity(), 2)
        self.assertTrue(room.is_available())
        self.assertEqual(room.availability_status(), "Partially Occupied")

    def test_TC_ROOM_02_cancelled_and_completed_allocations_do_not_count(self):
        room = self.make_room(capacity=2)
        self.allocate(room, status=Allocation.CANCELLED)
        self.allocate(room, status=Allocation.COMPLETED)
        self.assertEqual(room.available_capacity(), 2)
        self.assertEqual(room.availability_status(), "Available")

    def test_TC_ROOM_02_full_room_reports_full_and_not_available(self):
        """Boundary: last free bed is taken, room becomes Full."""
        room = self.make_room(capacity=1)
        self.allocate(room)
        self.assertEqual(room.available_capacity(), 0)
        self.assertFalse(room.is_available())
        self.assertEqual(room.availability_status(), "Full")

    def test_TC_ROOM_02_available_capacity_never_negative(self):
        room = self.make_room(capacity=1)
        self.allocate(room)
        self.allocate(room)  # data-integrity guard: stored over-allocation must not show negative beds
        self.assertEqual(room.available_capacity(), 0)


class RoomViewTests(RoomTestBase):
    def test_TC_ROOM_03_detail_shows_hostel_capacity_and_available_beds(self):
        """HMS-F-009: room number, hostel, capacity and available beds are displayed correctly."""
        room = self.make_room(number="105", capacity=3)
        self.allocate(room)
        self.client.force_login(self.student)
        response = self.client.get(reverse("rooms:detail", args=[room.pk]))
        self.assertContains(response, "105")
        self.assertContains(response, "Block A")
        self.assertContains(response, "Available beds")
        self.assertEqual(response.context["room"].available_capacity(), 2)

    def test_TC_ROOM_03_list_filters_by_hostel(self):
        self.make_room(number="101", hostel=self.hostel)
        self.make_room(number="901", hostel=self.other_hostel)
        self.client.force_login(self.student)
        response = self.client.get(reverse("rooms:list"), {"hostel": self.other_hostel.pk})
        numbers = [room.room_number for room in response.context["rooms"]]
        self.assertEqual(numbers, ["901"])

    def test_TC_ROOM_03_list_filters_by_floor(self):
        self.make_room(number="101", floor=1)
        self.make_room(number="201", floor=2)
        self.client.force_login(self.student)
        response = self.client.get(reverse("rooms:list"), {"floor": 2})
        self.assertEqual([r.room_number for r in response.context["rooms"]], ["201"])

    def test_TC_ROOM_03_list_filters_by_availability_status(self):
        empty = self.make_room(number="101", capacity=2)
        partial = self.make_room(number="102", capacity=2)
        full = self.make_room(number="103", capacity=1)
        self.allocate(partial)
        self.allocate(full)
        self.client.force_login(self.student)

        def numbers(status):
            response = self.client.get(reverse("rooms:list"), {"status": status})
            return sorted(r.room_number for r in response.context["rooms"])

        self.assertEqual(numbers("available"), ["101", "102"])  # partial still has a free bed
        self.assertEqual(numbers("partial"), ["102"])
        self.assertEqual(numbers("full"), ["103"])
        self.assertEqual(empty.availability_status(), "Available")

    def test_TC_ROOM_03_anonymous_user_cannot_see_rooms(self):
        response = self.client.get(reverse("rooms:list"))
        self.assertEqual(response.status_code, 302)

    def test_TC_ROOM_03_list_filters_by_invalid_floor_gracefully(self):
        """Non-numeric floor filter value is ignored gracefully (HMS-F-009)."""
        self.make_room(number="101", floor=1)
        self.client.force_login(self.student)
        response = self.client.get(reverse("rooms:list"), {"floor": "invalid-floor"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["rooms"]), 1)

    def test_TC_ROOM_01_string_representation(self):
        """Room __str__ returns formatted hostel-code and room-number."""
        room = self.make_room(number="101")
        self.assertEqual(str(room), "BLA-101")

    def test_TC_ROOM_02_active_allocation_count_fallback(self):
        """active_allocation_count queries directly when active_count annotation is absent."""
        room = self.make_room(capacity=2)
        self.allocate(room)
        # Fetch instance without with_active_counts()
        raw_room = Room.objects.filter(pk=room.pk).first()
        self.assertFalse(hasattr(raw_room, "active_count"))
        self.assertEqual(raw_room.active_allocation_count(), 1)

    def test_TC_ROOM_01_admin_views_room_update_form(self):
        """Admin GET request to room edit loads form populated with instance data."""
        room = self.make_room(number="303", capacity=2)
        self.client.force_login(self.admin)
        response = self.client.get(reverse("rooms:update", args=[room.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Edit room 303")

    def test_TC_ROOM_01_admin_update_invalid_data_shows_errors(self):
        """Submitting invalid data to room update re-renders with validation error."""
        room = self.make_room(number="304", capacity=2)
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("rooms:update", args=[room.pk]),
            {"hostel": self.hostel.pk, "room_number": "304", "capacity": 0, "floor": 1},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Capacity must be at least 1.")
