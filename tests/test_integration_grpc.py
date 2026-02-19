"""Integration tests for the synchronous gRPC client against a live ClamAV API.

These tests require a running ClamAV API service with gRPC enabled. Run with::

    pytest -m integration

Configure the gRPC address via the ``CLAMAV_GRPC_ADDR`` environment variable
(default: ``localhost:9000``).
"""

from __future__ import annotations

import os

import pytest

from clamav_sdk.grpc_client import ClamAVGRPCClient

pytestmark = pytest.mark.integration

EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
CLEAN_DATA = b"This is a clean test file with no malicious content."


@pytest.fixture(scope="module")
def grpc_addr() -> str:
    return os.environ.get("CLAMAV_GRPC_ADDR", "localhost:9000")


@pytest.fixture(scope="module")
def client(grpc_addr: str) -> ClamAVGRPCClient:
    c = ClamAVGRPCClient(target=grpc_addr)
    yield c  # type: ignore[misc]
    c.close()


class TestHealthCheck:
    def test_healthy(self, client: ClamAVGRPCClient):
        result = client.health_check()
        assert result.healthy is True


class TestScanFile:
    def test_clean_file(self, client: ClamAVGRPCClient):
        result = client.scan_file(CLEAN_DATA, filename="clean.txt")
        assert result.status == "OK"
        assert result.scan_time > 0

    def test_eicar_detected(self, client: ClamAVGRPCClient):
        result = client.scan_file(EICAR, filename="eicar.txt")
        assert result.status == "FOUND"
        assert "eicar" in result.message.lower()


class TestScanStream:
    def test_clean_stream(self, client: ClamAVGRPCClient):
        result = client.scan_stream(CLEAN_DATA, filename="stream-clean.txt", chunk_size=16)
        assert result.status == "OK"
        assert result.scan_time > 0

    def test_eicar_stream(self, client: ClamAVGRPCClient):
        result = client.scan_stream(EICAR, filename="stream-eicar.txt", chunk_size=16)
        assert result.status == "FOUND"
        assert "eicar" in result.message.lower()


class TestScanMultiple:
    def test_mixed_batch(self, client: ClamAVGRPCClient):
        files = [
            ("clean1.txt", CLEAN_DATA),
            ("eicar.txt", EICAR),
            ("clean2.txt", b"another safe payload"),
        ]
        results = client.scan_multiple(files, chunk_size=16)

        assert len(results) == 3
        assert results[0].status == "OK"
        assert results[0].filename == "clean1.txt"
        assert results[1].status == "FOUND"
        assert results[1].filename == "eicar.txt"
        assert "eicar" in results[1].message.lower()
        assert results[2].status == "OK"
        assert results[2].filename == "clean2.txt"
