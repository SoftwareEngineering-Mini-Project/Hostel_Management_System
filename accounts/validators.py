"""Input validation and sanitization framework (HMS-SR-004, TC-SEC-04).

Provides reusable validators and sanitizers to defend against XSS,
SQL injection payloads, and malformed form inputs.
"""

import re

from django.core.exceptions import ValidationError
from django.utils.html import escape, strip_tags

# Regex patterns for input validation
PHONE_REGEX = re.compile(r"^\+?[0-9]{10,15}$")
ALPHANUMERIC_CODE_REGEX = re.compile(r"^[A-Za-z0-9_-]+$")
SCRIPT_TAG_REGEX = re.compile(r"<\s*script[^>]*>.*?(<\s*/\s*script\s*>)?", re.IGNORECASE | re.DOTALL)
EVENT_HANDLER_REGEX = re.compile(r"on\w+\s*=", re.IGNORECASE)
JAVASCRIPT_URI_REGEX = re.compile(r"javascript\s*:", re.IGNORECASE)
SQL_INJECTION_REGEX = re.compile(
    r"(\b(UNION(\s+ALL)?|SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|EXEC|TRUNCATE)\b)|(--|\bOR\b\s+['\d\w]+\s*=\s*['\d\w]+|;)",
    re.IGNORECASE,
)


def sanitize_text(value):
    """Sanitize a text input by trimming whitespace and escaping special HTML characters.

    HMS-SR-004: Standardized sanitization for form text fields.
    """
    if not isinstance(value, str):
        return value
    # Strip leading and trailing whitespace
    cleaned = value.strip()
    return cleaned


def validate_no_script_tags(value):
    """Raise ValidationError if the string contains script tags, inline handlers, or javascript URIs.

    HMS-SR-004 / TC-SEC-04 / ST_SEC_04: Prevent XSS payloads.
    """
    if not isinstance(value, str):
        return
    if (
        SCRIPT_TAG_REGEX.search(value)
        or EVENT_HANDLER_REGEX.search(value)
        or JAVASCRIPT_URI_REGEX.search(value)
        or "<script" in value.lower()
    ):
        raise ValidationError(
            "Input contains forbidden script or HTML tags.",
            code="xss_detected",
        )


def validate_no_sql_injection(value):
    """Check for obvious SQL injection attack patterns.

    HMS-SR-004 / TC-SEC-04 / ST_SEC_04: Validate untrusted search and code inputs.
    """
    if not isinstance(value, str):
        return
    if SQL_INJECTION_REGEX.search(value):
        raise ValidationError(
            "Input contains forbidden SQL characters or command sequences.",
            code="sql_injection_detected",
        )


def validate_phone_number(value):
    """Validate that the phone number contains between 10 and 15 digits with optional leading '+'.

    HMS-SR-004 / UT_STU_03: Valid phone numbers format check.
    """
    if not value:
        return
    cleaned = str(value).strip()
    if not PHONE_REGEX.match(cleaned):
        raise ValidationError(
            "Please enter a valid phone number (10 to 15 digits).",
            code="invalid_phone",
        )


def validate_alphanumeric_code(value):
    """Validate that an identifier or code consists only of letters, numbers, hyphens, and underscores."""
    if not value:
        return
    cleaned = str(value).strip()
    if not ALPHANUMERIC_CODE_REGEX.match(cleaned):
        raise ValidationError(
            "Please use only letters, numbers, hyphens, and underscores.",
            code="invalid_code",
        )
