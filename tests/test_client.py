"""Tests for the synchronous REST client (ClamAVClient)."""

from __future__ import annotations

import io
import tempfile

import pytest
import responses

from clamav_sdk.client import ClamAVClient
from clamav_sdk.exceptions import (
    ClamAVBadRequestError,
    ClamAVConnectionError,
    ClamAVFileTooLargeError,
    ClamAVServiceUnavailableError,
    ClamAVTimeoutError,
)

BASE = "http://localhost:6000"


@pytest.fixture()
def client() -> ClamAVClient:
    return ClamAVClient(BASE)


# ------------------------------------------------------------------ #
# health_check
# ------------------------------------------------------------------ #


class TestHealthCheck:
    @responses.activate
    def test_healthy(self, client: ClamAVClient):
        responses.get(f"{BASE}/api/health-check", json={"message": "ok"}, status=200)
        result = client.health_check()
        assert result.healthy is True
        assert result.message == "ok"

    @responses.activate
    def test_unhealthy(self, client: ClamAVClient):
        responses.get(
            f"{BASE}/api/health-check",
            json={"message": "Clamd service unavailable"},
            status=502,
        )
        with pytest.raises(ClamAVServiceUnavailableError, match="Clamd service unavailable"):
            client.health_check()


# ------------------------------------------------------------------ #
# version
# ------------------------------------------------------------------ #


class TestVersion:
    @responses.activate
    def test_success(self, client: ClamAVClient):
        responses.get(
            f"{BASE}/api/version",
            json={"version": "1.3.0", "commit": "abc1234", "build": "2025-10-16T12:00:00Z"},
            status=200,
        )
        info = client.version()
        assert info.version == "1.3.0"
        assert info.commit == "abc1234"
        assert info.build == "2025-10-16T12:00:00Z"


# ------------------------------------------------------------------ #
# scan_file
# ------------------------------------------------------------------ #


class TestScanFile:
    @responses.activate
    def test_clean(self, client: ClamAVClient, sample_bytes: bytes):
        responses.post(
            f"{BASE}/api/scan",
            json={"status": "OK", "message": "", "time": 0.001},
            status=200,
        )
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
            tmp.write(sample_bytes)
            tmp.flush()
            result = client.scan_file(tmp.name)
        assert result.status == "OK"
        assert result.scan_time == pytest.approx(0.001)

    @responses.activate
    def test_virus_found(self, client: ClamAVClient, eicar_bytes: bytes):
        responses.post(
            f"{BASE}/api/scan",
            json={"status": "FOUND", "message": "Eicar-Test-Signature", "time": 0.002},
            status=200,
        )
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(eicar_bytes)
            tmp.flush()
            result = client.scan_file(tmp.name)
        assert result.status == "FOUND"
        assert result.message == "Eicar-Test-Signature"

    def test_file_not_found(self, client: ClamAVClient):
        with pytest.raises(FileNotFoundError):
            client.scan_file("/nonexistent/file.txt")

    @responses.activate
    def test_file_too_large(self, client: ClamAVClient, sample_bytes: bytes):
        responses.post(
            f"{BASE}/api/scan",
            json={"message": "File too large. Maximum size is 100 bytes"},
            status=413,
        )
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(sample_bytes)
            tmp.flush()
            with pytest.raises(ClamAVFileTooLargeError):
                client.scan_file(tmp.name)

    @responses.activate
    def test_timeout(self, client: ClamAVClient, sample_bytes: bytes):
        responses.post(
            f"{BASE}/api/scan",
            json={"status": "Scan timeout", "message": "scan operation timed out after 300 seconds"},
            status=504,
        )
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(sample_bytes)
            tmp.flush()
            with pytest.raises(ClamAVTimeoutError):
                client.scan_file(tmp.name)

    @responses.activate
    def test_service_unavailable(self, client: ClamAVClient, sample_bytes: bytes):
        responses.post(
            f"{BASE}/api/scan",
            json={"status": "Clamd service down", "message": "Scanning service unavailable"},
            status=502,
        )
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(sample_bytes)
            tmp.flush()
            with pytest.raises(ClamAVServiceUnavailableError):
                client.scan_file(tmp.name)


# ------------------------------------------------------------------ #
# scan_bytes
# ------------------------------------------------------------------ #


class TestScanBytes:
    @responses.activate
    def test_clean(self, client: ClamAVClient, sample_bytes: bytes):
        responses.post(
            f"{BASE}/api/scan",
            json={"status": "OK", "message": "", "time": 0.001},
            status=200,
        )
        result = client.scan_bytes(sample_bytes, filename="test.bin")
        assert result.status == "OK"

    @responses.activate
    def test_bad_request(self, client: ClamAVClient):
        responses.post(
            f"{BASE}/api/scan",
            json={"message": "Provide a single file"},
            status=400,
        )
        with pytest.raises(ClamAVBadRequestError, match="Provide a single file"):
            client.scan_bytes(b"")


# ------------------------------------------------------------------ #
# scan_stream
# ------------------------------------------------------------------ #


class TestScanStream:
    @responses.activate
    def test_bytes(self, client: ClamAVClient, sample_bytes: bytes):
        responses.post(
            f"{BASE}/api/stream-scan",
            json={"status": "OK", "message": "", "time": 0.0005},
            status=200,
        )
        result = client.scan_stream(sample_bytes)
        assert result.status == "OK"

    @responses.activate
    def test_binary_io(self, client: ClamAVClient, sample_bytes: bytes):
        responses.post(
            f"{BASE}/api/stream-scan",
            json={"status": "OK", "message": "", "time": 0.0005},
            status=200,
        )
        stream = io.BytesIO(sample_bytes)
        result = client.scan_stream(stream)
        assert result.status == "OK"

    @responses.activate
    def test_missing_content_length(self, client: ClamAVClient):
        responses.post(
            f"{BASE}/api/stream-scan",
            json={"message": "Content-Length header is required and must be greater than 0"},
            status=400,
        )
        with pytest.raises(ClamAVBadRequestError):
            client.scan_stream(b"")


# ------------------------------------------------------------------ #
# Connection error
# ------------------------------------------------------------------ #


class TestConnectionError:
    def test_unreachable_server(self):
        client = ClamAVClient("http://192.0.2.1:9999", timeout=0.5)
        with pytest.raises(ClamAVConnectionError):
            client.health_check()
