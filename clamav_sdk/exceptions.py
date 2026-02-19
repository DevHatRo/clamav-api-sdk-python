"""Exception hierarchy for the ClamAV SDK."""

from __future__ import annotations


class ClamAVError(Exception):
    """Base exception for all ClamAV SDK errors."""


class ClamAVConnectionError(ClamAVError):
    """Raised when the SDK cannot reach the ClamAV API server."""


class ClamAVTimeoutError(ClamAVError):
    """Raised when a scan operation times out.

    Corresponds to HTTP 504 or gRPC ``DEADLINE_EXCEEDED``.
    """


class ClamAVServiceUnavailableError(ClamAVError):
    """Raised when the ClamAV daemon is not running.

    Corresponds to HTTP 502 or gRPC ``INTERNAL`` with a clamd-unavailable message.
    """


class ClamAVFileTooLargeError(ClamAVError):
    """Raised when the uploaded file exceeds the server's size limit.

    Corresponds to HTTP 413 or gRPC ``INVALID_ARGUMENT`` with a size message.
    """


class ClamAVBadRequestError(ClamAVError):
    """Raised for malformed requests.

    Corresponds to HTTP 400 or gRPC ``INVALID_ARGUMENT``.
    """
