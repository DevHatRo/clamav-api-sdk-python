"""Integration tests for both async clients against a live ClamAV API.

These tests require a running ClamAV API service with both REST and gRPC
enabled. Run with::

    pytest -m integration

Configure via environment variables:
- ``CLAMAV_REST_URL`` (default: ``http://localhost:6000``)
- ``CLAMAV_GRPC_ADDR`` (default: ``localhost:9000``)
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from clamav_sdk.async_client import AsyncClamAVClient
from clamav_sdk.async_grpc_client import AsyncClamAVGRPCClient

pytestmark = pytest.mark.integration

EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
CLEAN_DATA = b"This is a clean test file with no malicious content."
TESTDATA_DIR = Path(__file__).resolve().parent.parent / "testdata"


# ------------------------------------------------------------------ #
# Async REST
# ------------------------------------------------------------------ #


class TestAsyncRESTHealthCheck:
    async def test_healthy(self):
        url = os.environ.get("CLAMAV_REST_URL", "http://localhost:6000")
        async with AsyncClamAVClient(url, timeout=60) as client:
            result = await client.health_check()
            assert result.healthy is True


class TestAsyncRESTVersion:
    async def test_returns_version(self):
        url = os.environ.get("CLAMAV_REST_URL", "http://localhost:6000")
        async with AsyncClamAVClient(url, timeout=60) as client:
            info = await client.version()
            assert info.version != ""


class TestAsyncRESTScanFile:
    async def test_clean_file(self):
        url = os.environ.get("CLAMAV_REST_URL", "http://localhost:6000")
        async with AsyncClamAVClient(url, timeout=60) as client:
            result = await client.scan_file(TESTDATA_DIR / "clean.txt")
            assert result.status == "OK"

    async def test_eicar_bytes(self):
        url = os.environ.get("CLAMAV_REST_URL", "http://localhost:6000")
        async with AsyncClamAVClient(url, timeout=60) as client:
            result = await client.scan_bytes(EICAR, filename="eicar.com")
            assert result.status == "FOUND"
            assert "eicar" in result.message.lower()


class TestAsyncRESTScanStream:
    async def test_clean_stream(self):
        url = os.environ.get("CLAMAV_REST_URL", "http://localhost:6000")
        async with AsyncClamAVClient(url, timeout=60) as client:
            result = await client.scan_stream(CLEAN_DATA)
            assert result.status == "OK"

    async def test_eicar_stream(self):
        url = os.environ.get("CLAMAV_REST_URL", "http://localhost:6000")
        async with AsyncClamAVClient(url, timeout=60) as client:
            result = await client.scan_stream(EICAR)
            assert result.status == "FOUND"


# ------------------------------------------------------------------ #
# Async gRPC
# ------------------------------------------------------------------ #


class TestAsyncGRPCHealthCheck:
    async def test_healthy(self):
        addr = os.environ.get("CLAMAV_GRPC_ADDR", "localhost:9000")
        async with AsyncClamAVGRPCClient(target=addr) as client:
            result = await client.health_check()
            assert result.healthy is True


class TestAsyncGRPCScanFile:
    async def test_clean_file(self):
        addr = os.environ.get("CLAMAV_GRPC_ADDR", "localhost:9000")
        async with AsyncClamAVGRPCClient(target=addr) as client:
            result = await client.scan_file(CLEAN_DATA, filename="async-clean.txt")
            assert result.status == "OK"

    async def test_eicar_file(self):
        addr = os.environ.get("CLAMAV_GRPC_ADDR", "localhost:9000")
        async with AsyncClamAVGRPCClient(target=addr) as client:
            result = await client.scan_file(EICAR, filename="async-eicar.txt")
            assert result.status == "FOUND"
            assert "eicar" in result.message.lower()


class TestAsyncGRPCScanStream:
    async def test_clean_stream(self):
        addr = os.environ.get("CLAMAV_GRPC_ADDR", "localhost:9000")
        async with AsyncClamAVGRPCClient(target=addr) as client:
            result = await client.scan_stream(CLEAN_DATA, filename="stream.txt", chunk_size=16)
            assert result.status == "OK"


class TestAsyncGRPCScanMultiple:
    async def test_mixed_batch(self):
        addr = os.environ.get("CLAMAV_GRPC_ADDR", "localhost:9000")
        async with AsyncClamAVGRPCClient(target=addr) as client:
            files = [
                ("clean.txt", CLEAN_DATA),
                ("eicar.txt", EICAR),
            ]
            results = []
            async for r in client.scan_multiple(files, chunk_size=16):
                results.append(r)

            assert len(results) == 2
            assert results[0].status == "OK"
            assert results[1].status == "FOUND"
            assert "eicar" in results[1].message.lower()
