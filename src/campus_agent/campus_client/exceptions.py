"""Errors raised by the CampusTrain HTTP client."""


class CampusClientError(RuntimeError):
    """Base error for transport and CampusTrain business failures."""


class CampusTransportError(CampusClientError):
    """The Gateway could not be reached or exceeded the configured timeout."""


class CampusHttpError(CampusClientError):
    """The Gateway returned an unsuccessful HTTP status."""

    def __init__(self, status_code: int, path: str, detail: str = "") -> None:
        self.status_code = status_code
        self.path = path
        self.detail = detail
        super().__init__(f"CampusTrain HTTP {status_code} for {path}: {detail}".strip())


class CampusBusinessError(CampusClientError):
    """CampusTrain returned a business-level failure in its response envelope."""

    def __init__(self, code: int | str | None, message: str, path: str) -> None:
        self.code = code
        self.message = message
        self.path = path
        super().__init__(f"CampusTrain business error for {path}: {code} {message}".strip())
