"""Extra edge-case tests for ClamAVClient to increase coverage."""

from __future__ import annotations

import pytest
import requests
import responses

from clamav_sdk.client import ClamAVClient
from clamav_sdk.exceptions import ClamAVConnectionError, ClamAVTimeoutError

BASE = "http://localhost:6000"


@pytest.fixture()
def client() -> ClamAVClient:
    return ClamAVClient(BASE)


class TestCustomSession:
    @responses.activate
    def test_custom_session(self):
        session = requests.Session()
        session.headers["X-Custom"] = "test"
        c = ClamAVClient(BASE, session=session)
        responses.get(f"{BASE}/api/health-check", json={"message": "ok"}, status=200)
        result = c.health_check()
        assert result.healthy is True


class TestScanFileConnectionError:
    @responses.activate
    def test_connection_error_on_scan(self, client: ClamAVClient, sample_bytes: bytes, tmp_path):
        f = tmp_path / "test.txt"
        f.write_bytes(sample_bytes)
        responses.post(f"{BASE}/api/scan", body=requests.ConnectionError("refused"))
        with pytest.raises(ClamAVConnectionError):
            client.scan_file(f)


class TestScanFileTimeout:
    @responses.activate
    def test_timeout_on_scan(self, client: ClamAVClient, sample_bytes: bytes, tmp_path):
        f = tmp_path / "test.txt"
        f.write_bytes(sample_bytes)
        responses.post(f"{BASE}/api/scan", body=requests.Timeout("timed out"))
        with pytest.raises(ClamAVTimeoutError):
            client.scan_file(f)


class TestStreamConnectionError:
    @responses.activate
    def test_connection_error_on_stream(self, client: ClamAVClient, sample_bytes: bytes):
        responses.post(f"{BASE}/api/stream-scan", body=requests.ConnectionError("refused"))
        with pytest.raises(ClamAVConnectionError):
            client.scan_stream(sample_bytes)


class TestStreamTimeout:
    @responses.activate
    def test_timeout_on_stream(self, client: ClamAVClient, sample_bytes: bytes):
        responses.post(f"{BASE}/api/stream-scan", body=requests.Timeout("timed out"))
        with pytest.raises(ClamAVTimeoutError):
            client.scan_stream(sample_bytes)


class TestGetConnectionError:
    @responses.activate
    def test_get_connection_error(self, client: ClamAVClient):
        responses.get(f"{BASE}/api/version", body=requests.ConnectionError("refused"))
        with pytest.raises(ClamAVConnectionError):
            client.version()


class TestGetTimeout:
    @responses.activate
    def test_get_timeout(self, client: ClamAVClient):
        responses.get(f"{BASE}/api/version", body=requests.Timeout("timed out"))
        with pytest.raises(ClamAVTimeoutError):
            client.version()


class TestRaiseForStatusUnknown:
    @responses.activate
    def test_unexpected_status_code(self, client: ClamAVClient):
        responses.get(f"{BASE}/api/version", json={"error": "nope"}, status=500)
        with pytest.raises(requests.HTTPError):
            client.version()


class TestTrailingSlashInBaseUrl:
    @responses.activate
    def test_strips_trailing_slash(self):
        c = ClamAVClient(f"{BASE}/")
        responses.get(f"{BASE}/api/health-check", json={"message": "ok"}, status=200)
        result = c.health_check()
        assert result.healthy is True
