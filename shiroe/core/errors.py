"""Typed errors for Zeref hardening gates."""

from __future__ import annotations


class ZerefError(ValueError):
    """Base error for user-actionable Zeref failures."""


class ValidationError(ZerefError):
    """Raised when structured memory data fails validation."""


class GuardRejection(ZerefError):
    """Raised when a guard blocks a requested operation."""

    def __init__(self, guard: str, reason: str, fix: str):
        super().__init__(f"Write blocked by {guard}.\n\nReason:\n{reason}\n\nFix:\n{fix}")
        self.guard = guard
        self.reason = reason
        self.fix = fix
