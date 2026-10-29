"""SEM-42 (QA-RTM): Room Allocation Module Unit and Integration Tests.

Test case IDs correspond to Test Plan Appendix A:
- TC-ALLOC-01 (UT_ALLOC_01, UT_ALLOC_02, IT_ALLOC_01, ST_ALLOC_01)
- TC-ALLOC-02 (UT_ALLOC_03, UT_ALLOC_04, UT_ALLOC_05, IT_ALLOC_02)
- TC-DATA-01 (UT_ALLOC_05, UT_AVL_03, ST_DATA_01)
- TC-REL-01 (Data Reliability and Persistence Safeguards)
"""

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

from allocations.models import Allocation
from dashboard.views import build_summary
from hostels.models import Hostel
from rooms.models import Room
from students.models import Student

User = get_user_model()


class AllocationModelUnitTests(TestCase):
    """Unit tests for the Allocation model structure, constraints, and methods (SEM-42, HMS-F-010)."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="PES1UG24AM101",
            password="TestPassword@123",
        )
        self.hostel = Hostel.objects.create(name="Block A", code="BLA", total_capacity=20)
        self.room = Room.objects.create(hostel=self.hostel, room_number="101", capacity=2)

    def test_TC_ALLOC_01_UT_ALLOC_01_allocation_creation_with_defaults(self):
        """Allocation model creates a record with default ACTIVE status and auto timestamp."""
        allocation = Allocation.objects.create(
            student=self.user,
            room=self.room,
        )
        self.assertEqual(allocation.status, Allocation.ACTIVE)
        self.assertEqual(allocation.student, self.user)
        self.assertEqual(allocation.room, self.room)
        self.assertIsNotNone(allocation.created_at)

    def test_TC_ALLOC_01_allocation_string_representation(self):
        """Allocation __str__ returns expected descriptive string format."""
        allocation = Allocation.objects.create(
            student=self.user,
            room=self.room,
            status=Allocation.ACTIVE,
        )
        expected = f"{self.user} in {self.room} (ACTIVE)"
        self.assertEqual(str(allocation), expected)

    def test_TC_ALLOC_01_status_choices_values(self):
        """Allocation status supports ACTIVE, COMPLETED, and CANCELLED choices."""
        alloc_active = Allocation.objects.create(
            student=self.user, room=self.room, status=Allocation.ACTIVE
        )
        alloc_completed = Allocation.objects.create(
            student=self.user, room=self.room, status=Allocation.COMPLETED
        )
        alloc_cancelled = Allocation.objects.create(
            student=self.user, room=self.room, status=Allocation.CANCELLED
        )

        self.assertEqual(alloc_active.status, "ACTIVE")
        self.assertEqual(alloc_completed.status, "COMPLETED")
        self.assertEqual(alloc_cancelled.status, "CANCELLED")

    def test_TC_REL_01_cascade_delete_on_room_deletion(self):
        """Deleting a room cascades and removes linked allocations."""
        Allocation.objects.create(student=self.user, room=self.room)
        self.assertEqual(Allocation.objects.count(), 1)

        self.room.delete()
        self.assertEqual(Allocation.objects.count(), 0)

    def test_TC_REL_01_cascade_delete_on_user_deletion(self):
        """Deleting a user cascades and removes their allocations."""
        Allocation.objects.create(student=self.user, room=self.room)
        self.assertEqual(Allocation.objects.count(), 1)

        self.user.delete()
        self.assertEqual(Allocation.objects.count(), 0)


class AllocationCapacityIntegrationTests(TestCase):
    """Integration tests connecting Allocation to Room availability, Student profile, and Dashboard."""

    def setUp(self):
        self.admin = User.objects.create_user("admin1", password="TestPassword@123", is_staff=True)
        self.u1 = User.objects.create_user("PES1UG24AM101", password="TestPassword@123")
        self.u2 = User.objects.create_user("PES1UG24AM102", password="TestPassword@123")
        self.student1 = Student.objects.create(
            user=self.u1,
            srn="PES1UG24AM101",
            name="Alice Smith",
            email="alice@pes.edu",
            phone="9876543210",
            gender=Student.FEMALE,
            department="CSE",
            year_of_study=2,
        )
        self.hostel = Hostel.objects.create(name="Block B", code="BLB", total_capacity=10)
        self.room = Room.objects.create(hostel=self.hostel, room_number="201", capacity=2)

    def test_TC_ALLOC_01_IT_ALLOC_01_active_allocation_reduces_room_capacity(self):
        """Creating an ACTIVE allocation immediately decreases room available capacity (HMS-F-008, HMS-F-010)."""
        self.assertEqual(self.room.available_capacity(), 2)
        self.assertEqual(self.room.availability_status(), "Available")

        # Allocate 1 bed
        Allocation.objects.create(student=self.u1, room=self.room, status=Allocation.ACTIVE)
        self.assertEqual(self.room.available_capacity(), 1)
        self.assertEqual(self.room.availability_status(), "Partially Occupied")

        # Allocate 2nd bed (room reaches full capacity)
        Allocation.objects.create(student=self.u2, room=self.room, status=Allocation.ACTIVE)
        self.assertEqual(self.room.available_capacity(), 0)
        self.assertFalse(self.room.is_available())
        self.assertEqual(self.room.availability_status(), "Full")

    def test_TC_ALLOC_02_UT_ALLOC_03_cancelled_allocations_do_not_reduce_capacity(self):
        """Cancelled and completed allocations release bed capacity (HMS-F-008, TC-ALLOC-02)."""
        alloc = Allocation.objects.create(student=self.u1, room=self.room, status=Allocation.ACTIVE)
        self.assertEqual(self.room.available_capacity(), 1)

        # Student checks out / allocation completed
        alloc.status = Allocation.COMPLETED
        alloc.save()
        self.assertEqual(self.room.available_capacity(), 2)
        self.assertEqual(self.room.availability_status(), "Available")

        # Allocation cancelled
        alloc.status = Allocation.CANCELLED
        alloc.save()
        self.assertEqual(self.room.available_capacity(), 2)

    def test_TC_ALLOC_01_student_current_allocation_integration(self):
        """Student model current_allocation() reflects active allocation linked to room and hostel."""
        # No allocation initially
        self.assertIsNone(self.student1.current_allocation())

        # Allocate room
        alloc = Allocation.objects.create(
            student=self.u1, room=self.room, status=Allocation.ACTIVE
        )
        curr = self.student1.current_allocation()
        self.assertIsNotNone(curr)
        self.assertEqual(curr.room.room_number, "201")
        self.assertEqual(curr.room.hostel.code, "BLB")

        # Mark completed -> current_allocation is None
        alloc.status = Allocation.COMPLETED
        alloc.save()
        self.assertIsNone(self.student1.current_allocation())

    def test_TC_ALLOC_01_dashboard_metrics_reflect_allocations(self):
        """Dashboard summary occupancy and available beds update with allocation records (HMS-F-019)."""
        initial_stats = build_summary()
        self.assertEqual(initial_stats["occupancy"], 0)
        self.assertEqual(initial_stats["available"], 2)

        # Add active allocation
        Allocation.objects.create(student=self.u1, room=self.room, status=Allocation.ACTIVE)
        updated_stats = build_summary()
        self.assertEqual(updated_stats["occupancy"], 1)
        self.assertEqual(updated_stats["available"], 1)

    def test_TC_DATA_01_active_count_annotation_consistency(self):
        """RoomQuerySet.with_active_counts matches stored allocations count."""
        Allocation.objects.create(student=self.u1, room=self.room, status=Allocation.ACTIVE)
        Allocation.objects.create(student=self.u2, room=self.room, status=Allocation.CANCELLED)

        annotated_room = Room.objects.with_active_counts().get(pk=self.room.pk)
        self.assertEqual(annotated_room.active_count, 1)
        self.assertEqual(annotated_room.available_capacity(), 1)
