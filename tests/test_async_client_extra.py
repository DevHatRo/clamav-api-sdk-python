"""Extra edge-case tests for AsyncClamAVClient to increase coverage."""

from __future__ import annotations

import io

import httpx
import pytest
import respx

from clamav_sdk.async_client import AsyncClamAVClient
from clamav_sdk.exceptions import (
    ClamAVConnectionError,
    ClamAVTimeoutError,
)

BASE = "http://localhost:6000"


class TestScanStreamBinaryIO:
    @respx.mock
    async def test_binary_io(self, sample_bytes: bytes):
        respx.post(f"{BASE}/api/stream-scan").respond(
            json={"status": "OK", "message": "", "time": 0.0005}
        )
        async with AsyncClamAVClient(BASE) as client:
            result = await client.scan_stream(io.BytesIO(sample_bytes))
            assert result.status == "OK"


class TestCustomHttpxClient:
    @respx.mock
    async def test_custom_client(self):
        respx.get(f"{BASE}/api/health-check").respond(json={"message": "ok"})
        custom = httpx.AsyncClient(timeout=10)
        c = AsyncClamAVClient(BASE, client=custom)
        result = await c.health_check()
        assert result.healthy is True
        await c.close()


class TestGetConnectionError:
    @respx.mock
    async def test_connect_error(self):
        respx.get(f"{BASE}/api/version").mock(side_effect=httpx.ConnectError("refused"))
        async with AsyncClamAVClient(BASE) as client:
            with pytest.raises(ClamAVConnectionError):
                await client.version()


class TestGetTimeout:
    @respx.mock
    async def test_timeout(self):
        respx.get(f"{BASE}/api/version").mock(side_effect=httpx.ReadTimeout("timed out"))
        async with AsyncClamAVClient(BASE) as client:
            with pytest.raises(ClamAVTimeoutError):
                await client.version()


class TestPostMultipartConnectionError:
    @respx.mock
    async def test_multipart_connect_error(self, sample_bytes: bytes):
        respx.post(f"{BASE}/api/scan").mock(side_effect=httpx.ConnectError("refused"))
        async with AsyncClamAVClient(BASE) as client:
            with pytest.raises(ClamAVConnectionError):
                await client.scan_bytes(sample_bytes)


class TestPostMultipartTimeout:
    @respx.mock
    async def test_multipart_timeout(self, sample_bytes: bytes):
        respx.post(f"{BASE}/api/scan").mock(side_effect=httpx.ReadTimeout("timed out"))
        async with AsyncClamAVClient(BASE) as client:
            with pytest.raises(ClamAVTimeoutError):
                await client.scan_bytes(sample_bytes)


class TestPostStreamConnectionError:
    @respx.mock
    async def test_stream_connect_error(self, sample_bytes: bytes):
        respx.post(f"{BASE}/api/stream-scan").mock(side_effect=httpx.ConnectError("refused"))
        async with AsyncClamAVClient(BASE) as client:
            with pytest.raises(ClamAVConnectionError):
                await client.scan_stream(sample_bytes)


class TestPostStreamTimeout:
    @respx.mock
    async def test_stream_timeout(self, sample_bytes: bytes):
        respx.post(f"{BASE}/api/stream-scan").mock(side_effect=httpx.ReadTimeout("timed out"))
        async with AsyncClamAVClient(BASE) as client:
            with pytest.raises(ClamAVTimeoutError):
                await client.scan_stream(sample_bytes)


class TestRaiseForStatusUnknown:
    @respx.mock
    async def test_unexpected_status_code(self):
        respx.get(f"{BASE}/api/version").respond(status_code=500, text="Internal Server Error")
        async with AsyncClamAVClient(BASE) as client:
            with pytest.raises(httpx.HTTPStatusError):
                await client.version()


class TestRaiseForStatusNonJsonBody:
    @respx.mock
    async def test_non_json_error_body(self):
        respx.get(f"{BASE}/api/health-check").respond(
            status_code=502, text="Bad Gateway", headers={"content-type": "text/plain"}
        )
        from clamav_sdk.exceptions import ClamAVServiceUnavailableError

        async with AsyncClamAVClient(BASE) as client:
            with pytest.raises(ClamAVServiceUnavailableError):
                await client.health_check()
