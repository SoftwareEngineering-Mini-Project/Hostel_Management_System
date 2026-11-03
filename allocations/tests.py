"""SEM-42 (QA-RTM): Room Allocation Module Unit and Integration Tests.

Test case IDs correspond to Test Plan Appendix A:
- TC-ALLOC-01 (UT_ALLOC_01, UT_ALLOC_02, IT_ALLOC_01, ST_ALLOC_01)
- TC-ALLOC-02 (UT_ALLOC_03, UT_ALLOC_04, UT_ALLOC_05, IT_ALLOC_02)
- TC-DATA-01 (UT_ALLOC_05, UT_AVL_03, ST_DATA_01)
- TC-REL-01 (Data Reliability and Persistence Safeguards)
- TC-ALLOC-03 (IT_STAT_01), TC-ALLOC-04 (UT_MOD_01, UT_MOD_02, ST_ALLOC_02), TC-ALLOC-05 (UT_CAN_01),
  TC-ALLOC-06 (UT_HIS_01, IT_HIS_01, ST_ALLOC_02)
"""

import threading

from django.contrib.auth import get_user_model
from django.db import IntegrityError, OperationalError, connection
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from allocations.models import Allocation, AllocationHistory
from allocations.services import (
    AlreadyAllocatedError,
    InvalidStateError,
    RoomFullError,
    allocate_room,
    cancel_allocation,
    modify_allocation,
)
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


def make_student(username, srn):
    user = User.objects.create_user(username, password="student-pass-123")
    Student.objects.create(
        user=user, srn=srn, name=f"Student {srn[-3:]}", email=f"{username}@pes.edu", phone="9876543210",
        gender=Student.FEMALE, department="CSE", year_of_study=2,
    )
    return user


class AllocationTestBase(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin1", password="admin-pass-123", is_staff=True)
        self.stu1 = make_student("stu1", "PES1UG24AM101")
        self.stu2 = make_student("stu2", "PES1UG24AM102")
        self.stu3 = make_student("stu3", "PES1UG24AM103")
        self.hostel = Hostel.objects.create(name="Block A", code="BLA", total_capacity=20)
        self.room = Room.objects.create(hostel=self.hostel, room_number="101", capacity=2)
        self.room2 = Room.objects.create(hostel=self.hostel, room_number="102", capacity=2)

    def login_admin(self):
        self.client.force_login(self.admin)

    def fill(self, room, *users):
        for user in users:
            Allocation.objects.create(student=user, room=room)


class AllocateRoomServiceTests(AllocationTestBase):
    def test_TC_ALLOC_01_UT_ALLOC_01_allocate_to_empty_room(self):
        allocation = allocate_room(self.stu1, self.room, self.admin)
        self.assertEqual(allocation.status, Allocation.ACTIVE)
        self.assertEqual(allocation.room, self.room)
        self.assertEqual(allocation.history.count(), 1)
        self.assertEqual(allocation.history.get().action, AllocationHistory.CREATED)
        self.assertEqual(self.room.available_capacity(), 1)

    def test_TC_ALLOC_01_UT_ALLOC_02_student_already_allocated_rejected(self):
        allocate_room(self.stu1, self.room, self.admin)
        with self.assertRaisesMessage(AlreadyAllocatedError, "Student already has an active allocation"):
            allocate_room(self.stu1, self.room2, self.admin)
        self.assertEqual(Allocation.objects.count(), 1)
        self.assertEqual(AllocationHistory.objects.count(), 1)

    def test_TC_ALLOC_02_UT_ALLOC_03_full_room_rejected(self):
        self.fill(self.room, self.stu1, self.stu2)
        with self.assertRaisesMessage(RoomFullError, "Room has reached its capacity"):
            allocate_room(self.stu3, self.room, self.admin)
        self.assertEqual(self.room.allocations.filter(status=Allocation.ACTIVE).count(), 2)
        self.assertFalse(Allocation.objects.filter(student=self.stu3).exists())

    def test_TC_ALLOC_02_UT_ALLOC_04_capacity_one_second_student_rejected(self):
        tiny = Room.objects.create(hostel=self.hostel, room_number="103", capacity=1)
        allocate_room(self.stu1, tiny, self.admin)
        with self.assertRaises(RoomFullError):
            allocate_room(self.stu2, tiny, self.admin)
        self.assertEqual(tiny.available_capacity(), 0)

    def test_TC_ALLOC_01_cancelled_student_can_be_allocated_again(self):
        allocation = allocate_room(self.stu1, self.room, self.admin)
        cancel_allocation(allocation, self.admin)
        again = allocate_room(self.stu1, self.room2, self.admin)
        self.assertEqual(again.room, self.room2)
        self.assertEqual(Allocation.objects.filter(student=self.stu1).count(), 2)


class AllocateRoomConcurrencyTests(TransactionTestCase):
    def test_TC_ALLOC_02_TC_DATA_01_UT_ALLOC_05_two_threads_one_bed(self):
        """Two requests for the last bed: exactly one wins, active count equals capacity.

        SQLite ignores select_for_update and serialises writers by locking the database, so a worker that hits
        'database is locked' retries; the retry then sees the committed allocation and gets RoomFullError.
        """
        admin = User.objects.create_user("admin1", password="x", is_staff=True)
        users = [make_student("t1", "PES1UG24AM201"), make_student("t2", "PES1UG24AM202")]
        room = Room.objects.create(
            hostel=Hostel.objects.create(name="Block B", code="BLB", total_capacity=5), room_number="1", capacity=1
        )
        barrier = threading.Barrier(2)
        outcomes = []

        def worker(user):
            try:
                barrier.wait(timeout=10)
                for _ in range(50):
                    try:
                        allocate_room(user, room, admin)
                        outcomes.append("ok")
                        return
                    except OperationalError:
                        continue  # SQLite database lock: try again once the other writer has finished
                    except RoomFullError:
                        outcomes.append("full")
                        return
                outcomes.append("gave-up")
            except Exception as error:  # pragma: no cover - surfaced by the assertions below
                outcomes.append(repr(error))
            finally:
                connection.close()

        threads = [threading.Thread(target=worker, args=(u,)) for u in users]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        self.assertEqual(sorted(outcomes), ["full", "ok"])
        self.assertEqual(room.allocations.filter(status=Allocation.ACTIVE).count(), 1)
        self.assertEqual(AllocationHistory.objects.filter(action=AllocationHistory.CREATED).count(), 1)


class ModifyAndCancelServiceTests(AllocationTestBase):
    def test_TC_ALLOC_04_UT_MOD_01_modify_to_room_with_free_bed(self):
        allocation = allocate_room(self.stu1, self.room, self.admin)
        modify_allocation(allocation, self.room2, self.admin)
        allocation.refresh_from_db()
        self.assertEqual(allocation.room, self.room2)
        self.assertEqual(allocation.status, Allocation.ACTIVE)
        self.assertEqual(self.room.available_capacity(), 2)
        self.assertEqual(self.room2.available_capacity(), 1)
        entry = allocation.history.filter(action=AllocationHistory.MODIFIED).get()
        self.assertEqual((entry.old_room, entry.new_room), (self.room, self.room2))

    def test_TC_ALLOC_04_UT_MOD_02_modify_to_full_room_rejected(self):
        allocation = allocate_room(self.stu1, self.room, self.admin)
        self.fill(self.room2, self.stu2, self.stu3)
        with self.assertRaisesMessage(RoomFullError, "Room has reached its capacity"):
            modify_allocation(allocation, self.room2, self.admin)
        allocation.refresh_from_db()
        self.assertEqual(allocation.room, self.room)
        self.assertFalse(allocation.history.filter(action=AllocationHistory.MODIFIED).exists())

    def test_TC_ALLOC_04_modify_to_same_room_rejected(self):
        allocation = allocate_room(self.stu1, self.room, self.admin)
        with self.assertRaisesMessage(InvalidStateError, "Student is already in this room"):
            modify_allocation(allocation, self.room, self.admin)

    def test_TC_ALLOC_04_modify_inactive_allocation_rejected(self):
        allocation = allocate_room(self.stu1, self.room, self.admin)
        cancel_allocation(allocation, self.admin)
        with self.assertRaisesMessage(InvalidStateError, "Allocation is not active"):
            modify_allocation(allocation, self.room2, self.admin)

    def test_TC_ALLOC_05_UT_CAN_01_cancel_frees_bed_and_keeps_row(self):
        allocation = allocate_room(self.stu1, self.room, self.admin)
        self.assertEqual(self.room.available_capacity(), 1)
        cancel_allocation(allocation, self.admin)
        allocation.refresh_from_db()
        self.assertEqual(allocation.status, Allocation.CANCELLED)
        self.assertEqual(allocation.history.latest("id").action, AllocationHistory.CANCELLED)
        self.assertEqual(self.room.available_capacity(), 2)
        self.assertTrue(Allocation.objects.filter(pk=allocation.pk).exists())

    def test_TC_ALLOC_05_cancel_twice_rejected(self):
        allocation = allocate_room(self.stu1, self.room, self.admin)
        cancel_allocation(allocation, self.admin)
        with self.assertRaisesMessage(InvalidStateError, "Allocation is not active"):
            cancel_allocation(allocation, self.admin)
        self.assertEqual(allocation.history.filter(action=AllocationHistory.CANCELLED).count(), 1)

    def test_TC_ALLOC_06_UT_HIS_01_history_records_each_change_by_admin(self):
        allocation = allocate_room(self.stu1, self.room, self.admin)
        modify_allocation(allocation, self.room2, self.admin)
        cancel_allocation(allocation, self.admin)
        rows = list(allocation.history.order_by("id"))
        self.assertEqual(
            [r.action for r in rows],
            [AllocationHistory.CREATED, AllocationHistory.MODIFIED, AllocationHistory.CANCELLED],
        )
        self.assertTrue(all(r.performed_by == self.admin for r in rows))
        self.assertEqual(rows[0].room_summary(), str(self.room))
        self.assertEqual(rows[1].room_summary(), f"{self.room} \u2192 {self.room2}")
        self.assertEqual(rows[2].room_summary(), str(self.room2))

    def test_TC_ALLOC_06_room_summary_falls_back_to_allocation_room(self):
        allocation = Allocation.objects.create(student=self.stu1, room=self.room)
        entry = AllocationHistory.objects.create(
            allocation=allocation, action=AllocationHistory.CHECKED_IN, performed_by=self.admin
        )
        self.assertEqual(entry.room_summary(), str(self.room))


class AllocationViewTests(AllocationTestBase):
    def test_TC_ALLOC_01_IT_ALLOC_01_admin_allocates_through_view(self):
        self.login_admin()
        response = self.client.post(
            reverse("allocations:create"), {"student": self.stu1.pk, "room": self.room.pk}, follow=True
        )
        self.assertRedirects(response, reverse("allocations:list"))
        self.assertContains(response, "Room allocated successfully")
        self.assertEqual(Allocation.objects.filter(student=self.stu1, status=Allocation.ACTIVE).count(), 1)

    def test_TC_ALLOC_02_IT_ALLOC_02_full_room_shows_error_and_saves_nothing(self):
        self.fill(self.room, self.stu1, self.stu2)
        self.login_admin()
        response = self.client.post(reverse("allocations:create"), {"student": self.stu3.pk, "room": self.room.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Room has reached its capacity")
        self.assertFalse(Allocation.objects.filter(student=self.stu3).exists())

    def test_TC_ALLOC_01_already_allocated_student_shows_error(self):
        self.fill(self.room, self.stu1)
        self.login_admin()
        response = self.client.post(reverse("allocations:create"), {"student": self.stu1.pk, "room": self.room2.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Student already has an active allocation")
        self.assertEqual(Allocation.objects.count(), 1)

    def test_TC_ALLOC_01_create_form_offers_only_free_students_and_rooms(self):
        self.fill(self.room, self.stu1, self.stu2)
        self.login_admin()
        response = self.client.get(reverse("allocations:create"))
        self.assertContains(response, "PES1UG24AM103")
        self.assertNotContains(response, "PES1UG24AM101")
        self.assertContains(response, "room 102")
        self.assertNotContains(response, "room 101")

    def test_TC_ALLOC_01_create_form_rejects_missing_fields(self):
        self.login_admin()
        response = self.client.post(reverse("allocations:create"), {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Allocation.objects.count(), 0)

    def test_TC_ALLOC_02_ST_ALLOC_01_fill_room_through_views_then_third_fails(self):
        self.login_admin()
        url = reverse("allocations:create")
        for user in (self.stu1, self.stu2):
            response = self.client.post(url, {"student": user.pk, "room": self.room.pk}, follow=True)
            self.assertContains(response, "Room allocated successfully")
        response = self.client.post(url, {"student": self.stu3.pk, "room": self.room.pk})
        self.assertContains(response, "Room has reached its capacity")
        self.assertEqual(self.room.allocations.filter(status=Allocation.ACTIVE).count(), 2)
        self.assertEqual(self.client.get(reverse("rooms:detail", args=[self.room.pk])).context["room"].availability_status(), "Full")
        self.assertContains(self.client.get(reverse("rooms:detail", args=[self.room.pk])), "Full")

    def test_TC_ALLOC_03_list_shows_allocations_with_links(self):
        allocation = Allocation.objects.create(student=self.stu1, room=self.room)
        self.login_admin()
        response = self.client.get(reverse("allocations:list"))
        self.assertContains(response, "Student 101")
        self.assertContains(response, reverse("allocations:detail", args=[allocation.pk]))
        self.assertContains(response, "Allocations</a>")

    def test_TC_ALLOC_03_empty_list(self):
        self.login_admin()
        self.assertContains(self.client.get(reverse("allocations:list")), "No allocations yet.")

    def test_TC_ALLOC_04_modify_view_moves_student(self):
        allocation = allocate_room(self.stu1, self.room, self.admin)
        self.login_admin()
        response = self.client.post(reverse("allocations:modify", args=[allocation.pk]), {"new_room": self.room2.pk}, follow=True)
        self.assertRedirects(response, reverse("allocations:detail", args=[allocation.pk]))
        self.assertContains(response, "Allocation updated successfully")
        allocation.refresh_from_db()
        self.assertEqual(allocation.room, self.room2)

    def test_TC_ALLOC_04_modify_view_full_room_shows_error(self):
        allocation = allocate_room(self.stu1, self.room, self.admin)
        self.fill(self.room2, self.stu2, self.stu3)
        self.login_admin()
        response = self.client.post(reverse("allocations:modify", args=[allocation.pk]), {"new_room": self.room2.pk}, follow=True)
        self.assertContains(response, "Room has reached its capacity")
        allocation.refresh_from_db()
        self.assertEqual(allocation.room, self.room)

    def test_TC_ALLOC_04_modify_view_without_room_shows_error(self):
        allocation = allocate_room(self.stu1, self.room, self.admin)
        self.login_admin()
        for data in ({}, {"new_room": "abc"}, {"new_room": 99999}):
            response = self.client.post(reverse("allocations:modify", args=[allocation.pk]), data, follow=True)
            self.assertContains(response, "Select a room to move the student to")

    def test_TC_ALLOC_04_modify_cancelled_allocation_shows_error(self):
        allocation = allocate_room(self.stu1, self.room, self.admin)
        cancel_allocation(allocation, self.admin)
        self.login_admin()
        response = self.client.post(reverse("allocations:modify", args=[allocation.pk]), {"new_room": self.room2.pk}, follow=True)
        self.assertContains(response, "Allocation is not active")

    def test_TC_ALLOC_04_modify_view_rejects_get(self):
        allocation = allocate_room(self.stu1, self.room, self.admin)
        self.login_admin()
        self.assertEqual(self.client.get(reverse("allocations:modify", args=[allocation.pk])).status_code, 405)

    def test_TC_ALLOC_05_cancel_get_shows_confirmation_and_changes_nothing(self):
        allocation = allocate_room(self.stu1, self.room, self.admin)
        self.login_admin()
        response = self.client.get(reverse("allocations:cancel", args=[allocation.pk]))
        self.assertContains(response, "Confirm cancellation")
        allocation.refresh_from_db()
        self.assertEqual(allocation.status, Allocation.ACTIVE)

    def test_TC_ALLOC_05_cancel_post_cancels(self):
        allocation = allocate_room(self.stu1, self.room, self.admin)
        self.login_admin()
        response = self.client.post(reverse("allocations:cancel", args=[allocation.pk]), follow=True)
        self.assertContains(response, "Allocation cancelled")
        allocation.refresh_from_db()
        self.assertEqual(allocation.status, Allocation.CANCELLED)

    def test_TC_ALLOC_05_cancel_non_active_shows_error(self):
        allocation = allocate_room(self.stu1, self.room, self.admin)
        cancel_allocation(allocation, self.admin)
        self.login_admin()
        response = self.client.post(reverse("allocations:cancel", args=[allocation.pk]), follow=True)
        self.assertContains(response, "Allocation is not active")

    def test_TC_ALLOC_05_detail_buttons_disabled_when_not_active(self):
        allocation = allocate_room(self.stu1, self.room, self.admin)
        self.login_admin()
        active_page = self.client.get(reverse("allocations:detail", args=[allocation.pk]))
        self.assertContains(active_page, reverse("allocations:cancel", args=[allocation.pk]))
        cancel_allocation(allocation, self.admin)
        page = self.client.get(reverse("allocations:detail", args=[allocation.pk]))
        self.assertNotContains(page, reverse("allocations:cancel", args=[allocation.pk]))
        self.assertContains(page, "disabled")

    def test_TC_ALLOC_06_detail_history_shows_old_and_new_room(self):
        allocation = allocate_room(self.stu1, self.room, self.admin)
        modify_allocation(allocation, self.room2, self.admin)
        self.login_admin()
        response = self.client.get(reverse("allocations:detail", args=[allocation.pk]))
        self.assertContains(response, f"{self.room} \u2192 {self.room2}")

    def test_TC_ALLOC_06_IT_HIS_01_history_filtered_by_student(self):
        a1 = allocate_room(self.stu1, self.room, self.admin)
        allocate_room(self.stu2, self.room2, self.admin)
        self.login_admin()
        response = self.client.get(reverse("allocations:history"), {"student": self.stu1.pk})
        entries = list(response.context["page"])
        self.assertEqual([e.allocation_id for e in entries], [a1.pk])
        self.assertContains(response, "Student 101")
        self.assertNotContains(response, "Student 102")

    def test_TC_ALLOC_06_history_filtered_by_room_includes_moves(self):
        allocation = allocate_room(self.stu1, self.room, self.admin)
        allocate_room(self.stu2, self.room, self.admin)
        modify_allocation(allocation, self.room2, self.admin)
        self.login_admin()
        in_room2 = self.client.get(reverse("allocations:history"), {"room": self.room2.pk}).context["page"]
        self.assertEqual([e.action for e in in_room2], [AllocationHistory.MODIFIED])
        in_room1 = self.client.get(reverse("allocations:history"), {"room": self.room.pk}).context["page"]
        self.assertEqual(len(list(in_room1)), 3)

    def test_TC_ALLOC_06_history_ignores_bad_filters_and_paginates(self):
        allocation = allocate_room(self.stu1, self.room, self.admin)
        for _ in range(13):
            modify_allocation(allocation, self.room2, self.admin)
            modify_allocation(allocation, self.room, self.admin)
        self.login_admin()
        response = self.client.get(reverse("allocations:history"), {"student": "x", "room": "y"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Next")
        page2 = self.client.get(reverse("allocations:history"), {"page": 2, "student": self.stu1.pk})
        self.assertContains(page2, "Previous")
        self.assertContains(page2, "student=")

    def test_TC_ALLOC_06_empty_history(self):
        self.login_admin()
        self.assertContains(self.client.get(reverse("allocations:history")), "No history found.")

    def test_TC_ALLOC_06_IT_HIS_01_student_gets_403_on_history(self):
        self.client.force_login(self.stu1)
        self.assertEqual(self.client.get(reverse("allocations:history")).status_code, 403)

    def test_TC_ALLOC_03_IT_STAT_01_student_home_shows_allocation_or_none(self):
        allocate_room(self.stu1, self.room, self.admin)
        self.client.force_login(self.stu1)
        response = self.client.get("/student/home/")
        self.assertContains(response, "Block A")
        self.assertContains(response, "room 101")
        self.assertContains(response, "not checked in")
        self.client.force_login(self.stu2)
        self.assertContains(self.client.get("/student/home/"), "No room allocated yet")

    def test_TC_ALLOC_04_TC_ALLOC_05_TC_ALLOC_06_ST_ALLOC_02_modify_cancel_history_flow(self):
        allocation = allocate_room(self.stu1, self.room, self.admin)
        self.login_admin()
        r = self.client.post(reverse("allocations:modify", args=[allocation.pk]), {"new_room": self.room2.pk}, follow=True)
        self.assertContains(r, "Allocation updated successfully")
        r = self.client.get(reverse("allocations:cancel", args=[allocation.pk]))
        self.assertContains(r, "Confirm cancellation")
        r = self.client.post(reverse("allocations:cancel", args=[allocation.pk]), follow=True)
        self.assertContains(r, "Allocation cancelled")
        r = self.client.get(reverse("allocations:history"), {"student": self.stu1.pk})
        self.assertEqual(
            [e.action for e in reversed(list(r.context["page"]))],
            [AllocationHistory.CREATED, AllocationHistory.MODIFIED, AllocationHistory.CANCELLED],
        )
        self.assertEqual(self.room2.available_capacity(), 2)


class AllocationAccessTests(AllocationTestBase):
    def urls(self):
        allocation = Allocation.objects.create(student=self.stu1, room=self.room)
        pk = allocation.pk
        return [
            reverse("allocations:list"),
            reverse("allocations:create"),
            reverse("allocations:history"),
            reverse("allocations:modify", args=[pk]),
            reverse("allocations:cancel", args=[pk]),
        ]

    def test_TC_SEC_02_students_get_403_on_every_allocation_url(self):
        urls = self.urls()
        self.client.force_login(self.stu1)
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 403, url)
            self.assertEqual(self.client.post(url).status_code, 403, url)

    def test_TC_SEC_01_anonymous_users_are_sent_to_login(self):
        for url in self.urls():
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, url)
            self.assertIn(reverse("login"), response["Location"], url)
        self.assertEqual(Allocation.objects.get().status, Allocation.ACTIVE)
