"""SEM-40 (QA-RTM): student module tests. Each test name carries its test case ID (STP section 8)."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from allocations.models import Allocation
from hostels.models import Hostel
from rooms.models import Room

from .forms import StudentRegistrationForm, StudentUpdateForm
from .models import Student
from .services import register_student, search_students, update_student

User = get_user_model()
PASSWORD = "Test@1234-hms"


def student_details(**overrides):
    data = {
        "srn": "PES1UG24AM999",
        "name": "Test Student",
        "email": "test@pes.edu",
        "phone": "9876543210",
        "gender": Student.FEMALE,
        "department": "AIML",
        "year_of_study": 2,
    }
    data.update(overrides)
    return data


def registration_payload(**overrides):
    data = student_details(password1=PASSWORD, password2=PASSWORD)
    data.update(overrides)
    return data


def make_student(**overrides):
    return register_student(password=PASSWORD, **student_details(**overrides))


class StudentFormTests(TestCase):
    def test_TC_STU_01_UT_STU_01_valid_details_are_saved(self):
        """HMS-F-003: a valid form creates one Student and a non-staff login named by SRN."""
        form = StudentRegistrationForm(registration_payload())
        self.assertTrue(form.is_valid(), form.errors)
        details = {k: v for k, v in form.cleaned_data.items() if not k.startswith("password")}
        register_student(password=form.cleaned_data["password1"], **details)

        student = Student.objects.get(srn="PES1UG24AM999")
        self.assertEqual(student.name, "Test Student")
        self.assertEqual(student.year_of_study, 2)
        self.assertEqual(student.user.username, "PES1UG24AM999")
        self.assertFalse(student.user.is_staff)
        self.assertTrue(student.user.check_password(PASSWORD))

    def test_TC_STU_01_UT_STU_02_duplicate_srn_is_rejected(self):
        make_student()
        form = StudentRegistrationForm(registration_payload())
        self.assertFalse(form.is_valid())
        self.assertIn("Student with this SRN already exists.", form.errors["srn"])
        self.assertEqual(Student.objects.count(), 1)

    def test_TC_STU_01_srn_is_normalised_to_upper_case(self):
        form = StudentRegistrationForm(registration_payload(srn=" pes1ug24am998 "))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["srn"], "PES1UG24AM998")

    def test_TC_STU_01_existing_login_with_same_srn_is_rejected(self):
        User.objects.create_user("PES1UG24AM999", password=PASSWORD)
        form = StudentRegistrationForm(registration_payload())
        self.assertFalse(form.is_valid())
        self.assertIn("A login account with this SRN already exists.", form.errors["srn"])

    def test_TC_STU_01_UT_STU_03_invalid_email_and_phone_are_rejected(self):
        """HMS-SR-004: server-side validation of email and phone."""
        form = StudentRegistrationForm(registration_payload(email="abc", phone="98ab12"))
        self.assertFalse(form.is_valid())
        self.assertIn("Enter a valid email address.", form.errors["email"])
        self.assertIn("Phone must be 10 digits.", form.errors["phone"])

    def test_TC_STU_01_year_of_study_out_of_range_is_rejected(self):
        form = StudentRegistrationForm(registration_payload(year_of_study=9))
        self.assertFalse(form.is_valid())
        self.assertIn("Year of study must be between 1 and 5.", form.errors["year_of_study"])

    def test_TC_STU_01_mismatched_passwords_are_rejected(self):
        form = StudentRegistrationForm(registration_payload(password2="Different@999"))
        self.assertFalse(form.is_valid())
        self.assertIn("The two passwords do not match.", form.errors["password2"])

    def test_TC_STU_01_weak_password_is_rejected(self):
        form = StudentRegistrationForm(registration_payload(password1="123", password2="123"))
        self.assertFalse(form.is_valid())
        self.assertIn("Password must be at least 8 characters.", form.errors["password1"])

    def test_TC_STU_02_UT_STU_04_updated_details_are_saved(self):
        """HMS-F-004: new phone and year are stored."""
        student = make_student()
        form = StudentUpdateForm(
            student_details(phone="9123456780", year_of_study=3), instance=student
        )
        self.assertTrue(form.is_valid(), form.errors)
        update_student(student, **form.cleaned_data)
        student.refresh_from_db()
        self.assertEqual(student.phone, "9123456780")
        self.assertEqual(student.year_of_study, 3)

    def test_TC_STU_02_email_change_updates_login_email(self):
        student = make_student()
        update_student(student, email="new@pes.edu")
        student.user.refresh_from_db()
        self.assertEqual(student.user.email, "new@pes.edu")


class StudentSearchTests(TestCase):
    def setUp(self):
        make_student(srn="PES1UG24AM101", name="Riya Rao")
        make_student(srn="PES1UG24AM102", name="Rahul Shah")

    def names(self, query):
        return [s.name for s in search_students(query)]

    def test_TC_STU_04_UT_STU_05_search_by_srn_or_name(self):
        """HMS-F-017: partial, case-insensitive match on SRN or name."""
        self.assertEqual(self.names("AM101"), ["Riya Rao"])
        self.assertEqual(self.names("riya"), ["Riya Rao"])
        self.assertEqual(self.names("zzzz"), [])

    def test_TC_STU_04_empty_query_returns_everyone(self):
        self.assertEqual(len(self.names("  ")), 2)

    def test_TC_STU_04_injection_text_is_treated_as_plain_text(self):
        """HMS-SR-004: search input never changes the query."""
        self.assertEqual(self.names("' OR 1=1 --"), [])


class StudentViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin1", password=PASSWORD, is_staff=True)
        self.riya = make_student(srn="PES1UG24AM101", name="Riya Rao")
        self.rahul = make_student(srn="PES1UG24AM102", name="Rahul Shah", email="rahul@pes.edu")

    def test_TC_STU_01_ST_STU_01_admin_registers_student(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("students:create"), registration_payload(), follow=True
        )
        self.assertRedirects(response, reverse("students:list"))
        self.assertContains(response, "Student Test Student was registered.")
        self.assertTrue(Student.objects.filter(srn="PES1UG24AM999").exists())

    def test_TC_STU_01_invalid_form_shows_errors(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("students:create"), registration_payload(phone="12"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Phone must be 10 digits.")
        self.assertFalse(Student.objects.filter(srn="PES1UG24AM999").exists())

    def test_TC_STU_02_ST_STU_01_admin_edits_student(self):
        self.client.force_login(self.admin)
        url = reverse("students:update", args=[self.riya.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(
            url, student_details(name="Riya Rao", phone="9000000001"), follow=True
        )
        self.assertRedirects(response, reverse("students:detail", args=[self.riya.pk]))
        self.assertContains(response, "9000000001")

    def test_TC_STU_04_ST_STU_01_admin_searches_students(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("students:list"), {"q": "rahul"})
        self.assertContains(response, "Rahul Shah")
        self.assertNotContains(response, "Riya Rao")

    def test_TC_STU_04_no_match_message(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("students:list"), {"q": "zzzz"})
        self.assertContains(response, "No students match")

    def test_TC_STU_03_IT_STU_02_student_sees_only_own_profile(self):
        """HMS-F-005: /student/home/ shows the logged-in student's own details."""
        self.client.force_login(self.riya.user)
        response = self.client.get(reverse("students:my_profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Riya Rao")
        self.assertNotContains(response, "Rahul Shah")
        self.assertContains(response, "No room allocated.")

    def test_TC_STU_03_profile_shows_active_room(self):
        hostel = Hostel.objects.create(name="Block A", code="BLA", total_capacity=2)
        room = Room.objects.create(hostel=hostel, room_number="A-101", capacity=2)
        Allocation.objects.create(student=self.riya.user, room=room)
        self.client.force_login(self.riya.user)
        response = self.client.get(reverse("students:my_profile"))
        self.assertContains(response, "Block A, room A-101")

    def test_TC_STU_03_user_without_student_record_gets_404(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("students:my_profile"))
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "No student record is linked to your account.", status_code=404)

    def test_TC_SEC_06_IT_STU_03_student_cannot_open_another_students_record(self):
        """HMS-SR-006: student pages by id are admin-only; a student gets 403 and no data."""
        self.client.force_login(self.riya.user)
        for name in ("students:update", "students:detail"):
            response = self.client.get(reverse(name, args=[self.rahul.pk]))
            self.assertEqual(response.status_code, 403)
            self.assertNotContains(response, "Rahul Shah", status_code=403)
        self.assertEqual(self.client.get(reverse("students:list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("students:create")).status_code, 403)

    def test_TC_SEC_06_student_cannot_change_another_students_record(self):
        self.client.force_login(self.riya.user)
        response = self.client.post(
            reverse("students:update", args=[self.rahul.pk]),
            student_details(name="Hacked", email="rahul@pes.edu"),
        )
        self.assertEqual(response.status_code, 403)
        self.rahul.refresh_from_db()
        self.assertEqual(self.rahul.name, "Rahul Shah")

    def test_TC_SEC_06_anonymous_user_is_sent_to_login(self):
        for url in (reverse("students:list"), reverse("students:my_profile")):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse("login"), response.url)

    def test_TC_UX_01_menus_link_to_student_pages_by_role(self):
        """HMS-NF-004: admin menu shows Students; student menu shows My profile only."""
        self.client.force_login(self.admin)
        response = self.client.get(reverse("students:list"))
        self.assertContains(response, reverse("students:list"))
        self.client.force_login(self.riya.user)
        response = self.client.get(reverse("students:my_profile"))
        self.assertContains(response, "My profile")
        self.assertNotContains(response, 'href="%s"' % reverse("students:list"))

    def test_TC_STU_01_student_string_representation(self):
        """Student model __str__ returns expected name (SRN) format."""
        self.assertEqual(str(self.riya), "Riya Rao (PES1UG24AM101)")

    def test_TC_STU_01_password_complexity_failure_in_clean(self):
        """Password >=8 chars but failing complexity validator adds form error (HMS-SR-003)."""
        payload = registration_payload(password1="12345678", password2="12345678")
        form = StudentRegistrationForm(payload)
        self.assertFalse(form.is_valid())
        self.assertIn("password1", form.errors)

    def test_TC_STU_02_admin_update_invalid_data_shows_errors(self):
        """Admin updating student with invalid phone displays form validation errors."""
        self.client.force_login(self.admin)
        url = reverse("students:update", args=[self.riya.pk])
        response = self.client.post(
            url, student_details(name="Riya Rao", phone="123")
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Phone must be 10 digits.")
