"""Errors raised by the CampusTrain HTTP client."""

import re


def safe_message(value: object) -> str:
    """Keep exception text useful without copying tokens or password values."""
    message = str(value)
    message = re.sub(r"(?i)bearer\s+[^\s,;]+", "Bearer [REDACTED]", message)
    message = re.sub(
        r"(?i)(password|token|jwt|secret)\s*[=:]\s*[^\s,;}]+",
        r"\1=[REDACTED]",
        message,
    )
    return message[:300]


class CampusClientError(RuntimeError):
    """Base error for transport and CampusTrain business failures."""


class CampusTransportError(CampusClientError):
    """The Gateway could not be reached or exceeded the configured timeout."""


class CampusHttpError(CampusClientError):
    """The Gateway returned an unsuccessful HTTP status."""

    def __init__(self, status_code: int, path: str, detail: str = "") -> None:
        self.status_code = status_code
        self.path = path
        self.detail = safe_message(detail)
        super().__init__(f"CampusTrain HTTP {status_code} for {path}: {self.detail}".strip())


class CampusBusinessError(CampusClientError):
    """CampusTrain returned a business-level failure in its response envelope."""

    def __init__(self, code: int | str | None, message: str, path: str) -> None:
        self.code = code
        self.message = safe_message(message)
        self.path = path
        super().__init__(f"CampusTrain business error for {path}: {code} {self.message}".strip())
