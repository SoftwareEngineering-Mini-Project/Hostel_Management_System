"""SEM-43 (QA-RTM): check-in and check-out tests. Each test name carries its test case ID (STP section 11).

- TC-CI-01 (UT_CI_01, UT_CI_02, UT_CI_03, IT_CI_01, ST_CICO_01) -> HMS-F-015
- TC-CO-01 (UT_CO_01, UT_CO_02, UT_CO_03, IT_CO_01, IT_CO_02, IT_CO_03, ST_CICO_01) -> HMS-F-016
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from hostels.models import Hostel
from rooms.models import Room
from students.models import Student

from .models import Allocation, AllocationHistory
from .services import InvalidStateError, check_in, check_out

User = get_user_model()


class CheckInOutTestBase(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin1", password="admin-pass-123", is_staff=True)
        self.stu_user = User.objects.create_user("stu1", password="student-pass-123")
        self.student = Student.objects.create(
            user=self.stu_user,
            srn="PES1UG24AM101",
            name="Asha Rao",
            email="asha@pes.edu",
            phone="9876543210",
            gender=Student.FEMALE,
            department="CSE",
            year_of_study=2,
        )
        self.hostel = Hostel.objects.create(name="Block A", code="BLA", total_capacity=20)
        self.room = Room.objects.create(hostel=self.hostel, room_number="101", capacity=1)
        self.allocation = Allocation.objects.create(student=self.stu_user, room=self.room)

    def history_actions(self):
        return list(self.allocation.history.values_list("action", flat=True))


class CheckInServiceTests(CheckInOutTestBase):
    def test_TC_CI_01_UT_CI_01_check_in_sets_date_and_history(self):
        """HMS-F-015: checking in an ACTIVE allocation records the time and a CHECKED_IN history row."""
        check_in(self.allocation, self.admin)
        self.allocation.refresh_from_db()
        self.assertIsNotNone(self.allocation.checked_in_on)
        self.assertEqual(self.allocation.status, Allocation.ACTIVE)
        entry = self.allocation.history.get()
        self.assertEqual(entry.action, AllocationHistory.CHECKED_IN)
        self.assertEqual(entry.performed_by, self.admin)
        self.assertEqual(str(entry), f"{self.allocation.pk} CHECKED_IN by admin1")

    def test_TC_CI_01_UT_CI_02_check_in_twice_is_rejected(self):
        check_in(self.allocation, self.admin)
        self.allocation.refresh_from_db()
        first_date = self.allocation.checked_in_on

        with self.assertRaisesMessage(InvalidStateError, "Student is already checked in"):
            check_in(self.allocation, self.admin)
        self.allocation.refresh_from_db()
        self.assertEqual(self.allocation.checked_in_on, first_date)
        self.assertEqual(self.history_actions(), [AllocationHistory.CHECKED_IN])

    def test_TC_CI_01_UT_CI_03_check_in_on_inactive_allocation_is_rejected(self):
        for status in (Allocation.CANCELLED, Allocation.COMPLETED):
            self.allocation.status = status
            self.allocation.save()
            with self.assertRaisesMessage(InvalidStateError, "Allocation is not active"):
                check_in(self.allocation, self.admin)
        self.allocation.refresh_from_db()
        self.assertIsNone(self.allocation.checked_in_on)
        self.assertEqual(self.history_actions(), [])

    def test_TC_CI_01_check_in_uses_stored_state_not_stale_object(self):
        """A stale in-memory copy cannot check in an allocation that was already checked in elsewhere."""
        stale = Allocation.objects.get(pk=self.allocation.pk)
        check_in(self.allocation, self.admin)
        with self.assertRaises(InvalidStateError):
            check_in(stale, self.admin)


class CheckOutServiceTests(CheckInOutTestBase):
    def test_TC_CO_01_UT_CO_01_check_out_completes_and_frees_bed(self):
        """HMS-F-016: check-out sets COMPLETED, records the time and history, and frees the bed."""
        check_in(self.allocation, self.admin)
        self.assertEqual(self.room.available_capacity(), 0)

        check_out(self.allocation, self.admin)
        self.allocation.refresh_from_db()
        self.assertEqual(self.allocation.status, Allocation.COMPLETED)
        self.assertIsNotNone(self.allocation.checked_out_on)
        self.assertEqual(self.room.available_capacity(), 1)
        self.assertEqual(
            self.history_actions(), [AllocationHistory.CHECKED_OUT, AllocationHistory.CHECKED_IN]
        )

    def test_TC_CO_01_UT_CO_02_check_out_before_check_in_is_rejected(self):
        with self.assertRaisesMessage(InvalidStateError, "Student is not checked in"):
            check_out(self.allocation, self.admin)
        self.allocation.refresh_from_db()
        self.assertEqual(self.allocation.status, Allocation.ACTIVE)
        self.assertIsNone(self.allocation.checked_out_on)
        self.assertEqual(self.room.available_capacity(), 0)

    def test_TC_CO_01_UT_CO_03_check_out_twice_is_rejected(self):
        check_in(self.allocation, self.admin)
        check_out(self.allocation, self.admin)
        with self.assertRaisesMessage(InvalidStateError, "Allocation is not active"):
            check_out(self.allocation, self.admin)
        self.assertEqual(self.history_actions().count(AllocationHistory.CHECKED_OUT), 1)

    def test_TC_CO_01_completed_allocation_is_kept_not_deleted(self):
        """ADR-06: check-out never deletes the allocation, so history stays traceable."""
        check_in(self.allocation, self.admin)
        check_out(self.allocation, self.admin)
        self.assertTrue(Allocation.objects.filter(pk=self.allocation.pk).exists())
        self.assertIsNone(self.student.current_allocation())


class CheckInOutViewTests(CheckInOutTestBase):
    def test_TC_CI_01_admin_checks_in_through_url(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("allocations:checkin", args=[self.allocation.pk]), follow=True)
        self.assertRedirects(response, reverse("allocations:detail", args=[self.allocation.pk]))
        self.assertContains(response, "Student checked in")
        self.allocation.refresh_from_db()
        self.assertIsNotNone(self.allocation.checked_in_on)

    def test_TC_CI_01_IT_CI_01_check_in_requires_post(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("allocations:checkin", args=[self.allocation.pk]))
        self.assertEqual(response.status_code, 405)
        self.allocation.refresh_from_db()
        self.assertIsNone(self.allocation.checked_in_on)

    def test_TC_CI_01_repeat_check_in_shows_error_message(self):
        check_in(self.allocation, self.admin)
        self.client.force_login(self.admin)
        response = self.client.post(reverse("allocations:checkin", args=[self.allocation.pk]), follow=True)
        self.assertContains(response, "Student is already checked in")

    def test_TC_CO_01_IT_CO_01_check_out_through_url_updates_availability(self):
        """Room with 0 free beds: POST /allocations/<id>/checkout/ redirects with a message and frees 1 bed."""
        check_in(self.allocation, self.admin)
        self.assertEqual(self.room.available_capacity(), 0)
        self.client.force_login(self.admin)

        response = self.client.post(reverse("allocations:checkout", args=[self.allocation.pk]))
        self.assertRedirects(
            response,
            reverse("allocations:detail", args=[self.allocation.pk]),
            fetch_redirect_response=False,
        )
        self.assertContains(self.client.get(response.url), "Student checked out")
        self.assertEqual(self.room.available_capacity(), 1)
        # Step 2 of IT_CO_01: the availability endpoint reports the freed bed.
        api = self.client.get(reverse("api_room_availability", args=[self.room.pk]))
        self.assertEqual(api.json()["available"], 1)

    def test_TC_CO_01_IT_CO_03_check_out_get_shows_confirmation_only(self):
        """SAD 3.5: a confirmation step comes before check-out; GET changes nothing."""
        check_in(self.allocation, self.admin)
        self.client.force_login(self.admin)
        response = self.client.get(reverse("allocations:checkout", args=[self.allocation.pk]))
        self.assertContains(response, "Confirm check-out")
        self.allocation.refresh_from_db()
        self.assertEqual(self.allocation.status, Allocation.ACTIVE)

    def test_TC_CO_01_check_out_before_check_in_shows_error_message(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("allocations:checkout", args=[self.allocation.pk]), follow=True)
        self.assertContains(response, "Student is not checked in")
        self.allocation.refresh_from_db()
        self.assertEqual(self.allocation.status, Allocation.ACTIVE)

    def test_TC_CO_01_IT_CO_02_student_cannot_check_in_or_out(self):
        """HMS-F-002: a logged-in student gets 403 and the allocation is unchanged."""
        self.client.force_login(self.stu_user)
        for name in ("allocations:checkin", "allocations:checkout", "allocations:detail"):
            response = self.client.post(reverse(name, args=[self.allocation.pk]))
            self.assertEqual(response.status_code, 403, name)
        self.allocation.refresh_from_db()
        self.assertIsNone(self.allocation.checked_in_on)
        self.assertEqual(self.allocation.status, Allocation.ACTIVE)

    def test_TC_CO_01_anonymous_user_is_sent_to_login(self):
        response = self.client.post(reverse("allocations:checkout", args=[self.allocation.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_TC_CO_01_unknown_allocation_returns_404(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("allocations:checkout", args=[9999]))
        self.assertEqual(response.status_code, 404)


class CheckInOutSystemTests(CheckInOutTestBase):
    def assert_buttons(self, check_in_enabled, check_out_enabled):
        response = self.client.get(reverse("allocations:detail", args=[self.allocation.pk]))
        html = response.content.decode()
        self.assertEqual('type="submit" >Check in' in html, check_in_enabled)
        self.assertEqual(
            f'href="{reverse("allocations:checkout", args=[self.allocation.pk])}"' in html, check_out_enabled
        )
        return response

    def test_TC_CI_01_TC_CO_01_ST_CICO_01_full_stay(self):
        """Allocate, check in, check out: buttons enabled only when allowed, bed free again at the end."""
        self.client.force_login(self.admin)
        self.assert_buttons(check_in_enabled=True, check_out_enabled=False)

        self.client.post(reverse("allocations:checkin", args=[self.allocation.pk]))
        self.assert_buttons(check_in_enabled=False, check_out_enabled=True)

        self.client.post(reverse("allocations:checkout", args=[self.allocation.pk]))
        response = self.assert_buttons(check_in_enabled=False, check_out_enabled=False)
        self.assertContains(response, "Completed")
        self.assertContains(response, "Checked out")
        self.assertEqual(self.room.available_capacity(), 1)

    def test_TC_CI_01_student_detail_links_to_allocation(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("students:detail", args=[self.student.pk]))
        self.assertContains(response, reverse("allocations:detail", args=[self.allocation.pk]))
        self.assertContains(response, "(not checked in)")

    def test_TC_CI_01_student_sees_own_check_in_status(self):
        check_in(self.allocation, self.admin)
        self.client.force_login(self.stu_user)
        response = self.client.get(reverse("students:my_profile"))
        self.assertContains(response, "(checked in")
