from __future__ import annotations


class NotFoundError(Exception):
    """Record is missing or not owned by the caller (same outward behavior)."""


class ValidationError(Exception):
    def __init__(self, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.field = field
