"""Tests for the asynchronous REST client (AsyncClamAVClient)."""

from __future__ import annotations

import tempfile

import httpx
import pytest
import respx

from clamav_sdk.async_client import AsyncClamAVClient
from clamav_sdk.exceptions import (
    ClamAVBadRequestError,
    ClamAVFileTooLargeError,
    ClamAVServiceUnavailableError,
    ClamAVTimeoutError,
)

BASE = "http://localhost:6000"


@pytest.fixture()
def client() -> AsyncClamAVClient:
    return AsyncClamAVClient(BASE)


class TestHealthCheck:
    @respx.mock
    async def test_healthy(self, client: AsyncClamAVClient):
        respx.get(f"{BASE}/api/health-check").respond(json={"message": "ok"})
        result = await client.health_check()
        assert result.healthy is True
        assert result.message == "ok"

    @respx.mock
    async def test_unhealthy(self, client: AsyncClamAVClient):
        respx.get(f"{BASE}/api/health-check").respond(
            json={"message": "Clamd service unavailable"}, status_code=502
        )
        with pytest.raises(ClamAVServiceUnavailableError):
            await client.health_check()


class TestVersion:
    @respx.mock
    async def test_success(self, client: AsyncClamAVClient):
        respx.get(f"{BASE}/api/version").respond(
            json={"version": "1.3.0", "commit": "abc1234", "build": "2025-10-16T12:00:00Z"}
        )
        info = await client.version()
        assert info.version == "1.3.0"


class TestScanFile:
    @respx.mock
    async def test_clean(self, client: AsyncClamAVClient, sample_bytes: bytes):
        respx.post(f"{BASE}/api/scan").respond(
            json={"status": "OK", "message": "", "time": 0.001}
        )
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
            tmp.write(sample_bytes)
            tmp.flush()
            result = await client.scan_file(tmp.name)
        assert result.status == "OK"

    async def test_file_not_found(self, client: AsyncClamAVClient):
        with pytest.raises(FileNotFoundError):
            await client.scan_file("/nonexistent/file.txt")


class TestScanBytes:
    @respx.mock
    async def test_clean(self, client: AsyncClamAVClient, sample_bytes: bytes):
        respx.post(f"{BASE}/api/scan").respond(
            json={"status": "OK", "message": "", "time": 0.001}
        )
        result = await client.scan_bytes(sample_bytes)
        assert result.status == "OK"

    @respx.mock
    async def test_bad_request(self, client: AsyncClamAVClient):
        respx.post(f"{BASE}/api/scan").respond(
            json={"message": "Provide a single file"}, status_code=400
        )
        with pytest.raises(ClamAVBadRequestError):
            await client.scan_bytes(b"")


class TestScanStream:
    @respx.mock
    async def test_bytes(self, client: AsyncClamAVClient, sample_bytes: bytes):
        respx.post(f"{BASE}/api/stream-scan").respond(
            json={"status": "OK", "message": "", "time": 0.0005}
        )
        result = await client.scan_stream(sample_bytes)
        assert result.status == "OK"

    @respx.mock
    async def test_too_large(self, client: AsyncClamAVClient, sample_bytes: bytes):
        respx.post(f"{BASE}/api/stream-scan").respond(
            json={"message": "File too large. Maximum size is 100 bytes"}, status_code=413
        )
        with pytest.raises(ClamAVFileTooLargeError):
            await client.scan_stream(sample_bytes)

    @respx.mock
    async def test_timeout(self, client: AsyncClamAVClient, sample_bytes: bytes):
        respx.post(f"{BASE}/api/stream-scan").respond(
            json={"message": "scan operation timed out"}, status_code=504
        )
        with pytest.raises(ClamAVTimeoutError):
            await client.scan_stream(sample_bytes)


class TestContextManager:
    @respx.mock
    async def test_aenter_aexit(self):
        respx.get(f"{BASE}/api/health-check").respond(json={"message": "ok"})
        async with AsyncClamAVClient(BASE) as client:
            result = await client.health_check()
            assert result.healthy is True
