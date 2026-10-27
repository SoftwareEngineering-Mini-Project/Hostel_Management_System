"""Authentication and Security QA Test Suite (SEM-39 / QA-AUTH).

Implements exhaustive automated test coverage for:
- HMS-F-001 (User Authentication): TC-AUTH-01 (UT_AUTH_01, UT_AUTH_02, ST_AUTH_01)
- HMS-F-002 (Role-Based Access Control): TC-AUTH-02 (UT_AUTH_04, IT_AUTH_03)
- HMS-SR-001 (Mandatory Authentication): TC-SEC-01 (IT_AUTH_02)
- HMS-SR-002 (Role-Based Admin Protection / IDOR): TC-SEC-02 (UT_AUTH_04, IT_AUTH_03, ST_SEC_02)
- HMS-SR-003 (Password Hashing & Plaintext Prevention): TC-SEC-03 (ST_SEC_01)
- HMS-SR-004 (Form Validation & Sanitization Framework): TC-SEC-04 (UT_STU_03, ST_SEC_04)
- HMS-SR-005 (Secure Session Management & Logout Invalidation): TC-SEC-05 (IT_AUTH_04)
- HMS-NF-005 (Modular Maintainable Architecture): TC-MAINT-01 (ST_MAINT_01)
"""

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from accounts.decorators import admin_required, is_admin, is_student, student_required
from accounts.forms import BootstrapFormMixin, LoginForm, SanitizedFormMixin
from accounts.services import authenticate_user, get_redirect_url_for_user, login_user, logout_user
from accounts.validators import (
    sanitize_text,
    validate_alphanumeric_code,
    validate_no_script_tags,
    validate_no_sql_injection,
    validate_phone_number,
)
from hostels.models import Hostel
from rooms.models import Room

User = get_user_model()


class AuthenticationModuleTests(TestCase):
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

    def test_TC_AUTH_01_UT_AUTH_01_valid_credentials_return_admin_user(self):
        """Valid admin credentials return User instance with is_staff=True (HMS-F-001)."""
        user = authenticate_user(None, "admin1", "TestPassword@123")
        self.assertIsNotNone(user)
        self.assertEqual(user.username, "admin1")
        self.assertTrue(user.is_staff)

    def test_TC_AUTH_01_UT_AUTH_01_valid_credentials_return_student_user(self):
        """Valid student credentials return User instance with is_staff=False (HMS-F-001)."""
        student = authenticate_user(None, "stu1", "TestPassword@123")
        self.assertIsNotNone(student)
        self.assertEqual(student.username, "stu1")
        self.assertFalse(student.is_staff)

    def test_TC_AUTH_01_UT_AUTH_02_wrong_password_rejected(self):
        """Wrong password returns None and does not create a session (HMS-F-001)."""
        user = authenticate_user(None, "admin1", "wrong123")
        self.assertIsNone(user)

    def test_TC_AUTH_01_UT_AUTH_02_nonexistent_user_rejected(self):
        """Nonexistent username returns None without revealing user existence (HMS-F-001)."""
        user = authenticate_user(None, "doesnotexist", "TestPassword@123")
        self.assertIsNone(user)

    def test_TC_AUTH_01_inactive_user_cannot_authenticate(self):
        """Inactive user account is rejected even with valid password (HMS-F-001)."""
        user = authenticate_user(None, "inactive1", "TestPassword@123")
        self.assertIsNone(user)

    def test_TC_AUTH_01_ST_AUTH_01_admin_login_lands_on_dashboard(self):
        """End-to-end login as admin lands on administrative dashboard (HMS-F-001, ST_AUTH_01)."""
        response = self.client.post(
            reverse("login"),
            {"username": "admin1", "password": "TestPassword@123"},
        )
        self.assertRedirects(response, reverse("dashboard:summary"))

    def test_TC_AUTH_01_ST_AUTH_01_student_login_lands_on_rooms(self):
        """End-to-end login as student lands on room availability (HMS-F-001, ST_AUTH_01)."""
        response = self.client.post(
            reverse("login"),
            {"username": "stu1", "password": "TestPassword@123"},
        )
        self.assertRedirects(response, reverse("rooms:list"))

    def test_TC_AUTH_01_ST_AUTH_01_wrong_password_displays_error(self):
        """Login failure displays clear error feedback (HMS-F-001, ST_AUTH_01)."""
        response = self.client.post(
            reverse("login"),
            {"username": "admin1", "password": "wrong123"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid username or password.")

    def test_TC_AUTH_01_login_preserves_safe_next_url(self):
        """Login safely redirects to requested internal ?next= path (HMS-F-001)."""
        response = self.client.post(
            f"{reverse('login')}?next=/rooms/",
            {"username": "stu1", "password": "TestPassword@123"},
        )
        self.assertRedirects(response, "/rooms/")

    def test_TC_AUTH_01_open_redirect_protection(self):
        """Malicious external next parameter redirects to safe internal role default (HMS-F-001, HMS-SR-004)."""
        malicious_urls = [
            "https://evil.com",
            "//evil.com",
            "javascript:alert(1)",
        ]
        for url in malicious_urls:
            target = get_redirect_url_for_user(self.student_user, next_url=url)
            self.assertEqual(target, "/rooms/")

    def test_TC_AUTH_01_authenticated_user_accessing_login_redirected(self):
        """Authenticated users visiting /accounts/login/ are redirected to their landing page."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("login"))
        self.assertRedirects(response, reverse("dashboard:summary"))


class RoleBasedAccessControlTests(TestCase):
    """HMS-F-002 / TC-AUTH-02: Role-Based Access Control (@admin_required, @student_required)."""

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

    def test_TC_AUTH_02_role_predicates(self):
        """is_admin and is_student accurately verify role state."""
        self.assertTrue(is_admin(self.admin_user))
        self.assertFalse(is_student(self.admin_user))
        self.assertTrue(is_student(self.student_user))
        self.assertFalse(is_admin(self.student_user))

        anon = AnonymousUser()
        self.assertFalse(is_admin(anon))
        self.assertFalse(is_student(anon))

    def test_TC_AUTH_02_UT_AUTH_04_admin_required_allows_admin(self):
        """@admin_required allows admin request (HMS-F-002, UT_AUTH_04)."""
        @admin_required
        def sample_admin_view(request):
            return HttpResponse("admin authorized")

        request = self.factory.get("/admin-path/")
        request.user = self.admin_user
        response = sample_admin_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"admin authorized")

    def test_TC_AUTH_02_UT_AUTH_04_admin_required_blocks_student(self):
        """@admin_required raises PermissionDenied (403) for student (HMS-F-002, UT_AUTH_04)."""
        @admin_required
        def sample_admin_view(request):
            return HttpResponse("admin authorized")

        request = self.factory.get("/admin-path/")
        request.user = self.student_user
        with self.assertRaises(PermissionDenied):
            sample_admin_view(request)

    def test_TC_AUTH_02_admin_required_redirects_anonymous_user(self):
        """@admin_required redirects unauthenticated requests to login."""
        @admin_required
        def sample_admin_view(request):
            return HttpResponse("admin authorized")

        request = self.factory.get("/admin-path/")
        request.user = AnonymousUser()
        response = sample_admin_view(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_TC_AUTH_02_student_required_allows_student(self):
        """@student_required allows student requests (HMS-F-002)."""
        @student_required
        def sample_student_view(request):
            return HttpResponse("student authorized")

        request = self.factory.get("/student-path/")
        request.user = self.student_user
        response = sample_student_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"student authorized")

    def test_TC_AUTH_02_student_required_blocks_admin(self):
        """@student_required raises PermissionDenied (403) for admin (HMS-F-002)."""
        @student_required
        def sample_student_view(request):
            return HttpResponse("student authorized")

        request = self.factory.get("/student-path/")
        request.user = self.admin_user
        with self.assertRaises(PermissionDenied):
            sample_student_view(request)

    def test_TC_AUTH_02_student_required_redirects_anonymous_user(self):
        """@student_required redirects unauthenticated requests to login."""
        @student_required
        def sample_student_view(request):
            return HttpResponse("student authorized")

        request = self.factory.get("/student-path/")
        request.user = AnonymousUser()
        response = sample_student_view(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])


class MandatoryAuthSecurityTests(TestCase):
    """HMS-SR-001 / TC-SEC-01 / IT_AUTH_02: Mandatory Authentication for Protected Functions."""

    def test_TC_SEC_01_IT_AUTH_02_protected_routes_require_authentication(self):
        """Unauthenticated requests to protected endpoints redirect to login with ?next=."""
        endpoints = [
            reverse("rooms:list"),
            reverse("hostels:list"),
            reverse("hostels:create"),
            reverse("rooms:create"),
            reverse("dashboard:summary"),
        ]
        for url in endpoints:
            response = self.client.get(url)
            self.assertEqual(
                response.status_code,
                302,
                f"Endpoint {url} did not redirect unauthenticated request",
            )
            self.assertIn(reverse("login"), response["Location"])
            self.assertIn(f"next={url}", response["Location"])


class RoleAuthorizationAdminProtectionTests(TestCase):
    """HMS-SR-002 / TC-SEC-02 / IT_AUTH_03 / ST_SEC_02: Role-based admin page enforcement & IDOR prevention."""

    def setUp(self):
        self.admin = User.objects.create_user("admin1", password="TestPassword@123", is_staff=True)
        self.student = User.objects.create_user("stu1", password="TestPassword@123", is_staff=False)
        self.hostel = Hostel.objects.create(name="Block C", code="BLC", total_capacity=20)
        self.room = Room.objects.create(hostel=self.hostel, room_number="101", capacity=2)

    def test_TC_SEC_02_IT_AUTH_03_ST_SEC_02_student_cannot_access_any_admin_page(self):
        """Student session gets HTTP 403 on all administrator endpoints (IT_AUTH_03, ST_SEC_02)."""
        self.client.force_login(self.student)
        admin_urls = [
            reverse("dashboard:summary"),
            reverse("hostels:list"),
            reverse("hostels:create"),
            reverse("hostels:detail", args=[self.hostel.pk]),
            reverse("hostels:update", args=[self.hostel.pk]),
            reverse("rooms:create"),
            reverse("rooms:update", args=[self.room.pk]),
        ]
        for url in admin_urls:
            response = self.client.get(url)
            self.assertEqual(
                response.status_code,
                403,
                f"Student was unexpectedly permitted access to admin URL: {url}",
            )

    def test_TC_SEC_02_IT_AUTH_03_student_cannot_post_to_admin_creation_endpoints(self):
        """Student session cannot create resources via admin POST endpoints (IT_AUTH_03)."""
        self.client.force_login(self.student)

        # Attempt to create hostel
        post_hostel = self.client.post(
            reverse("hostels:create"),
            {"name": "Unauthorized Hostel", "code": "UNAUTH", "total_capacity": 10},
        )
        self.assertEqual(post_hostel.status_code, 403)
        self.assertFalse(Hostel.objects.filter(code="UNAUTH").exists())

        # Attempt to create room
        post_room = self.client.post(
            reverse("rooms:create"),
            {"hostel": self.hostel.pk, "room_number": "999", "capacity": 2},
        )
        self.assertEqual(post_room.status_code, 403)
        self.assertFalse(Room.objects.filter(room_number="999").exists())


class PasswordSecurityStorageTests(TestCase):
    """HMS-SR-003 / TC-SEC-03 / ST_SEC_01: Secure Password Hashing & Plaintext Prevention."""

    def test_TC_SEC_03_ST_SEC_01_passwords_stored_hashed_with_pbkdf2(self):
        """Passwords in database are hashed with PBKDF2 (pbkdf2_sha256$) and never plaintext (ST_SEC_01)."""
        raw_password = "SuperSecretPassword#2026"
        user = User.objects.create_user(username="sec_user", password=raw_password)

        # Inspect raw database password representation
        self.assertTrue(user.password.startswith("pbkdf2_sha256$"))
        self.assertNotIn(raw_password, user.password)

        # Verify password validation works
        self.assertTrue(user.check_password(raw_password))
        self.assertFalse(user.check_password("wrongpass"))

    def test_TC_SEC_03_ST_SEC_01_different_users_with_same_password_have_unique_hashes(self):
        """Salting ensures identical passwords have distinct hash signatures."""
        user1 = User.objects.create_user(username="u1", password="CommonPassword123#")
        user2 = User.objects.create_user(username="u2", password="CommonPassword123#")
        self.assertNotEqual(user1.password, user2.password)

    def test_TC_SEC_03_password_complexity_validators(self):
        """Password validators reject short, entirely numeric, or common passwords."""
        with self.assertRaises(ValidationError):
            validate_password("short", user=None)
        with self.assertRaises(ValidationError):
            validate_password("12345678", user=None)
        with self.assertRaises(ValidationError):
            validate_password("password", user=None)


class SessionSecurityManagementTests(TestCase):
    """HMS-SR-005 / TC-SEC-05 / IT_AUTH_04: Secure Session Management & Logout Invalidation."""

    def setUp(self):
        self.user = User.objects.create_user("sess_user", password="TestPassword@123")

    def test_TC_SEC_05_IT_AUTH_04_logout_invalidates_session_and_clears_cookie(self):
        """Logging out flushes the session so the previous session cookie cannot access protected views (IT_AUTH_04)."""
        # Step 1: Login
        self.client.post(
            reverse("login"),
            {"username": "sess_user", "password": "TestPassword@123"},
        )
        self.assertEqual(self.client.get(reverse("rooms:list")).status_code, 200)

        # Step 2: Logout
        logout_response = self.client.post(reverse("logout"))
        self.assertRedirects(logout_response, reverse("login"))

        # Step 3: Access protected URL with stale session
        retry_response = self.client.get(reverse("rooms:list"))
        self.assertEqual(retry_response.status_code, 302)
        self.assertIn(reverse("login"), retry_response["Location"])

    def test_TC_SEC_05_session_security_settings(self):
        """Session cookies are configured with HttpOnly and browser close expiry flags."""
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertTrue(settings.SESSION_EXPIRE_AT_BROWSER_CLOSE)
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)


class InputSanitizationAndValidationTests(TestCase):
    """HMS-SR-004 / TC-SEC-04 / ST_SEC_04: Form Validation & Input Sanitization Framework."""

    def test_TC_SEC_04_ST_SEC_04_xss_payloads_rejected(self):
        """XSS attack vectors are rejected by validate_no_script_tags (ST_SEC_04)."""
        attacks = [
            "<script>alert('xss')</script>",
            "<script src='https://malicious.example/evil.js'></script>",
            "<SCRIPT>alert(1)</SCRIPT>",
            "<img src=x onerror=alert('xss')>",
            "<body onload=alert('xss')>",
            "<a href='javascript:alert(1)'>click me</a>",
        ]
        for payload in attacks:
            with self.assertRaises(ValidationError, msg=f"Failed to reject payload: {payload}"):
                validate_no_script_tags(payload)

    def test_TC_SEC_04_sanitize_text_utility(self):
        """sanitize_text removes leading and trailing whitespace."""
        self.assertEqual(sanitize_text("   hello world   "), "hello world")
        self.assertEqual(sanitize_text("  \t\n  "), "")

    def test_TC_SEC_04_phone_number_validation(self):
        """validate_phone_number validates correct phone format and blocks invalid characters (UT_STU_03)."""
        valid_phones = ["9876543210", "+919876543210", "123456789012"]
        for p in valid_phones:
            self.assertIsNone(validate_phone_number(p))

        invalid_phones = ["98ab12", "12345", "phone123", "+12345"]
        for p in invalid_phones:
            with self.assertRaises(ValidationError, msg=f"Accepted invalid phone: {p}"):
                validate_phone_number(p)

    def test_TC_SEC_04_alphanumeric_code_validation(self):
        """validate_alphanumeric_code enforces valid code formatting."""
        self.assertIsNone(validate_alphanumeric_code("BLA-101"))
        self.assertIsNone(validate_alphanumeric_code("PES1UG24AM346"))
        with self.assertRaises(ValidationError):
            validate_alphanumeric_code("BLA 101")
        with self.assertRaises(ValidationError):
            validate_alphanumeric_code("BLA; DROP TABLE")

    def test_TC_SEC_04_sql_injection_detection(self):
        """validate_no_sql_injection detects common SQL injection attack strings."""
        sqli_payloads = [
            "' OR 1=1 --",
            "admin' --",
            "UNION SELECT username, password FROM auth_user",
            "1; DROP TABLE auth_user",
        ]
        for payload in sqli_payloads:
            with self.assertRaises(ValidationError, msg=f"Failed to detect SQLi: {payload}"):
                validate_no_sql_injection(payload)

    def test_TC_SEC_04_sanitized_form_mixin_integration(self):
        """Forms subclassing SanitizedFormMixin strip whitespace and block XSS."""
        class TestContactForm(SanitizedFormMixin, forms.Form):
            subject = forms.CharField()
            message = forms.CharField()

        # Valid form trims spaces
        form = TestContactForm(data={"subject": "  Hostel Request  ", "message": "  Details here  "})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["subject"], "Hostel Request")
        self.assertEqual(form.cleaned_data["message"], "Details here")

        # Invalid form with script tag
        xss_form = TestContactForm(data={"subject": "Normal", "message": "<script>alert(1)</script>"})
        self.assertFalse(xss_form.is_valid())
        self.assertIn("forbidden script or HTML tags", str(xss_form.errors))

    def test_TC_SEC_04_ST_SEC_04_csrf_token_required_on_post(self):
        """Submitting a form POST without CSRF token returns HTTP 403 Forbidden (ST_SEC_04)."""
        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post(
            reverse("login"),
            {"username": "admin1", "password": "password"},
        )
        self.assertEqual(response.status_code, 403)


class ModularArchitectureMaintenanceTests(TestCase):
    """HMS-NF-005 / TC-MAINT-01 / ST_MAINT_01: Modular decoupled Django architecture."""

    def test_TC_MAINT_01_ST_MAINT_01_installed_apps_decoupled(self):
        """Verify that all core apps are independently registered in INSTALLED_APPS."""
        expected_apps = ["accounts", "hostels", "rooms", "allocations", "dashboard"]
        for app in expected_apps:
            self.assertIn(app, settings.INSTALLED_APPS)
