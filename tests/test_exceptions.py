"""Tests for clamav_sdk.exceptions."""

from clamav_sdk.exceptions import (
    ClamAVBadRequestError,
    ClamAVConnectionError,
    ClamAVError,
    ClamAVFileTooLargeError,
    ClamAVServiceUnavailableError,
    ClamAVTimeoutError,
)


def test_hierarchy():
    assert issubclass(ClamAVConnectionError, ClamAVError)
    assert issubclass(ClamAVTimeoutError, ClamAVError)
    assert issubclass(ClamAVServiceUnavailableError, ClamAVError)
    assert issubclass(ClamAVFileTooLargeError, ClamAVError)
    assert issubclass(ClamAVBadRequestError, ClamAVError)


def test_base_is_exception():
    assert issubclass(ClamAVError, Exception)


def test_message_preserved():
    exc = ClamAVFileTooLargeError("File too large. Maximum size is 100 bytes")
    assert "100" in str(exc)
