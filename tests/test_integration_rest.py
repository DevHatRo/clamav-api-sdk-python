"""Integration tests for the synchronous REST client against a live ClamAV API.

These tests require a running ClamAV API service. Run with::

    pytest -m integration

Configure the service URL via the ``CLAMAV_REST_URL`` environment variable
(default: ``http://localhost:6000``).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from clamav_sdk.client import ClamAVClient

pytestmark = pytest.mark.integration

EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
CLEAN_DATA = b"This is a clean test file with no malicious content."
TESTDATA_DIR = Path(__file__).resolve().parent.parent / "testdata"


@pytest.fixture(scope="module")
def rest_url() -> str:
    return os.environ.get("CLAMAV_REST_URL", "http://localhost:6000")


@pytest.fixture(scope="module")
def client(rest_url: str) -> ClamAVClient:
    return ClamAVClient(rest_url, timeout=60)


class TestHealthCheck:
    def test_healthy(self, client: ClamAVClient):
        result = client.health_check()
        assert result.healthy is True
        assert result.message == "ok"


class TestVersion:
    def test_returns_version_info(self, client: ClamAVClient):
        info = client.version()
        assert info.version != ""
        assert info.commit != ""
        assert info.build != ""


class TestScanFile:
    def test_clean_file(self, client: ClamAVClient):
        result = client.scan_file(TESTDATA_DIR / "clean.txt")
        assert result.status == "OK"
        assert result.scan_time > 0

    def test_eicar_detected(self, client: ClamAVClient, tmp_path: Path):
        eicar_path = tmp_path / "eicar.com"
        eicar_path.write_bytes(EICAR)
        result = client.scan_file(eicar_path)
        assert result.status == "FOUND"
        assert "eicar" in result.message.lower()


class TestScanBytes:
    def test_clean_bytes(self, client: ClamAVClient):
        result = client.scan_bytes(CLEAN_DATA, filename="clean.txt")
        assert result.status == "OK"

    def test_eicar_bytes(self, client: ClamAVClient):
        result = client.scan_bytes(EICAR, filename="eicar.com")
        assert result.status == "FOUND"
        assert "eicar" in result.message.lower()


class TestScanStream:
    def test_clean_stream(self, client: ClamAVClient):
        result = client.scan_stream(CLEAN_DATA)
        assert result.status == "OK"
        assert result.scan_time > 0

    def test_eicar_stream(self, client: ClamAVClient):
        result = client.scan_stream(EICAR)
        assert result.status == "FOUND"
        assert "eicar" in result.message.lower()
