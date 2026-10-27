"""Authentication and Access Control Tests (HMS-F-001, HMS-F-002, HMS-SR-001, HMS-SR-002).

Test case IDs correspond to Test Plan Appendix A:
- TC-AUTH-01 (UT_AUTH_01, UT_AUTH_02, ST_AUTH_01)
- TC-AUTH-02 (UT_AUTH_04, IT_AUTH_03)
- TC-SEC-01 (IT_AUTH_02)
- TC-SEC-02 (UT_AUTH_04, IT_AUTH_03, ST_SEC_02)
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse

from accounts.decorators import admin_required, is_admin, is_student, student_required
from accounts.forms import LoginForm
from accounts.services import authenticate_user

User = get_user_model()


class AuthenticationTests(TestCase):
    """HMS-F-001 / TC-AUTH-01: User authentication for administrators and students."""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="admin1",
            password="TestPassword@123",
            is_staff=True,
        )
        self.student_user = User.objects.create_user(
            username="stu1",
            password="TestPassword@123",
            is_staff=False,
        )
        self.inactive_user = User.objects.create_user(
            username="inactive1",
            password="TestPassword@123",
            is_active=False,
        )

    def test_TC_AUTH_01_UT_AUTH_01_valid_credentials_return_user(self):
        """Valid credentials return the User instance."""
        user = authenticate_user(None, "admin1", "TestPassword@123")
        self.assertIsNotNone(user)
        self.assertEqual(user.username, "admin1")
        self.assertTrue(user.is_staff)

        student = authenticate_user(None, "stu1", "TestPassword@123")
        self.assertIsNotNone(student)
        self.assertEqual(student.username, "stu1")
        self.assertFalse(student.is_staff)

    def test_TC_AUTH_01_UT_AUTH_02_wrong_password_rejected(self):
        """Invalid credentials return None and do not authenticate."""
        user = authenticate_user(None, "admin1", "WrongPassword")
        self.assertIsNone(user)

        user_nonexistent = authenticate_user(None, "nonexistent", "TestPassword@123")
        self.assertIsNone(user_nonexistent)

    def test_TC_AUTH_01_inactive_user_cannot_authenticate(self):
        """Inactive user credentials return None."""
        user = authenticate_user(None, "inactive1", "TestPassword@123")
        self.assertIsNone(user)

    def test_TC_AUTH_01_ST_AUTH_01_login_view_redirects_admin_to_dashboard(self):
        """Admin login redirects to administrative dashboard."""
        response = self.client.post(
            reverse("login"),
            {"username": "admin1", "password": "TestPassword@123"},
        )
        self.assertRedirects(response, reverse("dashboard:summary"))

    def test_TC_AUTH_01_ST_AUTH_01_login_view_redirects_student_to_rooms(self):
        """Student login redirects to room availability list."""
        response = self.client.post(
            reverse("login"),
            {"username": "stu1", "password": "TestPassword@123"},
        )
        self.assertRedirects(response, reverse("rooms:list"))

    def test_TC_AUTH_01_login_view_honors_safe_next_parameter(self):
        """Login preserves and redirects to safe next target URL."""
        response = self.client.post(
            f"{reverse('login')}?next=/rooms/",
            {"username": "stu1", "password": "TestPassword@123"},
        )
        self.assertRedirects(response, "/rooms/")

    def test_TC_AUTH_01_login_view_rejects_invalid_login_with_message(self):
        """Failed login displays error message and HTTP 200."""
        response = self.client.post(
            reverse("login"),
            {"username": "admin1", "password": "wrongpassword"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid username or password.")

    def test_TC_AUTH_01_already_logged_in_user_redirected(self):
        """Accessing login page while already authenticated redirects away."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("login"))
        self.assertRedirects(response, reverse("dashboard:summary"))


class RoleBasedAccessControlTests(TestCase):
    """HMS-F-002 / TC-AUTH-02: Role-based access control decorators and helpers."""

    def setUp(self):
        self.factory = RequestFactory()
        self.admin_user = User.objects.create_user(
            username="admin1",
            password="TestPassword@123",
            is_staff=True,
        )
        self.student_user = User.objects.create_user(
            username="stu1",
            password="TestPassword@123",
            is_staff=False,
        )

    def test_TC_AUTH_02_role_check_helpers(self):
        """Helper functions is_admin and is_student identify roles correctly."""
        self.assertTrue(is_admin(self.admin_user))
        self.assertFalse(is_student(self.admin_user))

        self.assertTrue(is_student(self.student_user))
        self.assertFalse(is_admin(self.student_user))

    def test_TC_AUTH_02_UT_AUTH_04_admin_required_allows_admin(self):
        """@admin_required allows requests from staff users."""
        @admin_required
        def dummy_view(request):
            return HttpResponse("admin ok")

        request = self.factory.get("/admin-only/")
        request.user = self.admin_user
        response = dummy_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"admin ok")

    def test_TC_AUTH_02_UT_AUTH_04_admin_required_denies_student(self):
        """@admin_required raises PermissionDenied (403) for student users."""
        @admin_required
        def dummy_view(request):
            return HttpResponse("admin ok")

        request = self.factory.get("/admin-only/")
        request.user = self.student_user
        with self.assertRaises(PermissionDenied):
            dummy_view(request)

    def test_TC_AUTH_02_admin_required_redirects_anonymous_to_login(self):
        """@admin_required redirects unauthenticated users to login page."""
        @admin_required
        def dummy_view(request):
            return HttpResponse("admin ok")

        from django.contrib.auth.models import AnonymousUser

        request = self.factory.get("/admin-only/")
        request.user = AnonymousUser()
        response = dummy_view(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_TC_AUTH_02_student_required_allows_student(self):
        """@student_required allows requests from non-staff students."""
        @student_required
        def dummy_view(request):
            return HttpResponse("student ok")

        request = self.factory.get("/student-only/")
        request.user = self.student_user
        response = dummy_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"student ok")

    def test_TC_AUTH_02_student_required_denies_admin(self):
        """@student_required raises PermissionDenied (403) for admin users."""
        @student_required
        def dummy_view(request):
            return HttpResponse("student ok")

        request = self.factory.get("/student-only/")
        request.user = self.admin_user
        with self.assertRaises(PermissionDenied):
            dummy_view(request)


class MandatoryAuthAndAdminProtectionTests(TestCase):
    """HMS-SR-001 (TC-SEC-01) & HMS-SR-002 (TC-SEC-02)."""

    def setUp(self):
        self.student_user = User.objects.create_user(
            username="stu1",
            password="TestPassword@123",
            is_staff=False,
        )

    def test_TC_SEC_01_IT_AUTH_02_mandatory_authentication_for_protected_pages(self):
        """Protected pages redirect unauthenticated requests to login with ?next= (HMS-SR-001)."""
        protected_urls = [
            reverse("rooms:list"),
            reverse("hostels:list"),
            reverse("dashboard:summary"),
        ]
        for url in protected_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse("login"), response["Location"])
            self.assertIn(f"next={url}", response["Location"])

    def test_TC_SEC_02_IT_AUTH_03_student_session_cannot_reach_admin_pages(self):
        """Student session gets HTTP 403 on administrator-only endpoints (HMS-SR-002)."""
        self.client.force_login(self.student_user)
        admin_urls = [
            reverse("dashboard:summary"),
            reverse("hostels:list"),
            reverse("hostels:create"),
            reverse("rooms:create"),
        ]
        for url in admin_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403, f"Student accessed admin url: {url}")
