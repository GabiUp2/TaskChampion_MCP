"""Input sanitization for all values passed to subprocess CLI calls.

Defence-in-depth layer on top of subprocess argument-list invocation (ADR 9).
Every string destined for a `task` or `timew` CLI argument passes through here.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# Characters that must never appear in any CLI argument value.
# Subprocess argument lists prevent shell interpretation, but Taskwarrior
# itself may interpret certain characters in filter expressions.
_DANGEROUS_CHARS = re.compile(r"[\x00-\x08\x0e-\x1f]")  # control chars (except \t \n \r)

# Shell metacharacters — blocked to prevent any residual risk even though
# we never use shell=True.  Backticks, $(), ;, &&, ||, pipes, redirects.
_SHELL_META = re.compile(r"[`$;|&<>]|(\$\()")

# URL-encoded shell metacharacters (defense-in-depth).
_URL_ENCODED_META = re.compile(r"%(?:26|7[cC]|3[bB]|60|24|3[eE]|3[cC])")

# Taskwarrior filter injection — patterns that could alter filter semantics
# when placed inside a value that is naively concatenated into a filter string.
_FILTER_INJECTION = re.compile(r"\b(or|and|xor|not)\b", re.IGNORECASE)

# Valid tag pattern: alphanumeric, hyphens, underscores, dots, up to 64 chars
_TAG_PATTERN = re.compile(r"^[a-zA-Z0-9._-]{1,64}$")

# Valid project pattern: dot-separated segments, alphanumeric + hyphens
_PROJECT_PATTERN = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?$")

# UUID v4 pattern
_UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

# Maximum length for any single field value
MAX_FIELD_LENGTH = 1024
MAX_DESCRIPTION_LENGTH = 4096
MAX_ANNOTATION_LENGTH = 4096


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class SanitizationError(ValueError):
    """Raised when input fails sanitization checks."""


# ---------------------------------------------------------------------------
# Core sanitization
# ---------------------------------------------------------------------------


def _check_control_chars(value: str, field_name: str) -> None:
    if _DANGEROUS_CHARS.search(value):
        raise SanitizationError(f"Field '{field_name}' contains prohibited control characters.")


def _check_null_bytes(value: str, field_name: str) -> None:
    if "\x00" in value:
        raise SanitizationError(f"Field '{field_name}' contains null bytes.")


def _check_shell_meta(value: str, field_name: str) -> None:
    if _SHELL_META.search(value):
        raise SanitizationError(
            f"Field '{field_name}' contains shell metacharacters "
            f"(backticks, $, ;, |, &, <, >). Value: {value!r:.80}"
        )
    if _URL_ENCODED_META.search(value):
        raise SanitizationError(f"Field '{field_name}' contains URL-encoded shell metacharacters.")


def sanitize_description(value: str) -> str:
    """Sanitize a task description."""
    if not value or not value.strip():
        raise SanitizationError("Description must not be empty.")
    if len(value) > MAX_DESCRIPTION_LENGTH:
        raise SanitizationError(
            f"Description exceeds maximum length of {MAX_DESCRIPTION_LENGTH} characters."
        )
    _check_null_bytes(value, "description")
    _check_control_chars(value, "description")
    _check_shell_meta(value, "description")
    return value.strip()


def sanitize_annotation(value: str) -> str:
    """Sanitize an annotation string."""
    if not value or not value.strip():
        raise SanitizationError("Annotation must not be empty.")
    if len(value) > MAX_ANNOTATION_LENGTH:
        raise SanitizationError(
            f"Annotation exceeds maximum length of {MAX_ANNOTATION_LENGTH} characters."
        )
    _check_null_bytes(value, "annotation")
    _check_control_chars(value, "annotation")
    _check_shell_meta(value, "annotation")
    return value.strip()


def sanitize_tag(value: str) -> str:
    """Sanitize a single tag value (without the + prefix)."""
    tag = value.lstrip("+")
    if not _TAG_PATTERN.match(tag):
        raise SanitizationError(
            f"Tag '{value}' is invalid. Tags must be 1-64 alphanumeric characters, "
            f"hyphens, underscores, or dots."
        )
    return tag


def sanitize_project(value: str) -> str:
    """Sanitize a project name (dot-notation hierarchy)."""
    if not value:
        raise SanitizationError("Project name must not be empty.")
    if len(value) > 256:
        raise SanitizationError("Project name exceeds maximum length of 256 characters.")
    _check_null_bytes(value, "project")
    if not _PROJECT_PATTERN.match(value):
        raise SanitizationError(
            f"Project name '{value}' is invalid. Must be alphanumeric with dots, "
            f"hyphens, or underscores."
        )
    segments = value.split(".")
    if len(segments) > 6:
        raise SanitizationError(f"Project '{value}' has {len(segments)} levels (max 6).")
    return value


def sanitize_uuid(value: str) -> str:
    """Validate and return a UUID string."""
    if not _UUID_PATTERN.match(value):
        raise SanitizationError(f"Invalid UUID format: {value!r:.48}")
    return value.lower()


def sanitize_enum(value: str, field_name: str, allowed: list[str]) -> str:
    """Validate an enumerated field value."""
    if value not in allowed:
        raise SanitizationError(
            f"Field '{field_name}' value '{value}' is not in allowed values: {allowed}"
        )
    return value


def sanitize_field_value(value: str, field_name: str) -> str:
    """Generic sanitization for UDA and other free-text field values."""
    if len(value) > MAX_FIELD_LENGTH:
        raise SanitizationError(
            f"Field '{field_name}' exceeds maximum length of {MAX_FIELD_LENGTH} characters."
        )
    _check_null_bytes(value, field_name)
    _check_control_chars(value, field_name)
    _check_shell_meta(value, field_name)
    return value.strip()


def sanitize_filter_expression(value: str) -> str:
    """Sanitize a Taskwarrior filter expression.

    Filters are passed as separate arguments to `task`, so shell injection
    is not a concern. However, we still block control characters and
    excessively long strings.
    """
    if len(value) > MAX_FIELD_LENGTH:
        raise SanitizationError("Filter expression too long.")
    _check_null_bytes(value, "filter")
    _check_control_chars(value, "filter")
    return value.strip()
