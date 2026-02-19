"""Extra edge-case tests for gRPC error handling to increase coverage."""

from __future__ import annotations

from unittest.mock import MagicMock

import grpc
import pytest

from clamav_sdk.exceptions import (
    ClamAVBadRequestError,
    ClamAVConnectionError,
    ClamAVError,
    ClamAVFileTooLargeError,
    ClamAVServiceUnavailableError,
    ClamAVTimeoutError,
)
from clamav_sdk.grpc_client import _handle_rpc_error


def _make_rpc_error(code: grpc.StatusCode, details: str) -> grpc.RpcError:
    exc = grpc.RpcError()
    exc.code = MagicMock(return_value=code)  # type: ignore[method-assign]
    exc.details = MagicMock(return_value=details)  # type: ignore[method-assign]
    return exc


class TestHandleRpcError:
    def test_unavailable(self):
        with pytest.raises(ClamAVConnectionError, match="refused"):
            _handle_rpc_error(_make_rpc_error(grpc.StatusCode.UNAVAILABLE, "refused"))

    def test_deadline_exceeded(self):
        with pytest.raises(ClamAVTimeoutError, match="timed out"):
            _handle_rpc_error(_make_rpc_error(grpc.StatusCode.DEADLINE_EXCEEDED, "timed out"))

    def test_internal(self):
        with pytest.raises(ClamAVServiceUnavailableError, match="daemon"):
            _handle_rpc_error(_make_rpc_error(grpc.StatusCode.INTERNAL, "daemon error"))

    def test_internal_unavailable(self):
        with pytest.raises(ClamAVServiceUnavailableError, match="unavailable"):
            _handle_rpc_error(_make_rpc_error(grpc.StatusCode.INTERNAL, "clamd unavailable"))

    def test_invalid_argument_too_large(self):
        with pytest.raises(ClamAVFileTooLargeError, match="too large"):
            _handle_rpc_error(_make_rpc_error(grpc.StatusCode.INVALID_ARGUMENT, "file too large"))

    def test_invalid_argument_generic(self):
        with pytest.raises(ClamAVBadRequestError, match="bad field"):
            _handle_rpc_error(_make_rpc_error(grpc.StatusCode.INVALID_ARGUMENT, "bad field"))

    def test_cancelled(self):
        with pytest.raises(ClamAVError, match="cancelled"):
            _handle_rpc_error(_make_rpc_error(grpc.StatusCode.CANCELLED, "cancelled"))

    def test_unknown_code(self):
        with pytest.raises(ClamAVError, match="UNKNOWN"):
            _handle_rpc_error(_make_rpc_error(grpc.StatusCode.UNKNOWN, "something went wrong"))
