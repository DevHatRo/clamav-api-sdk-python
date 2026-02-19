"""Tests for the asynchronous gRPC client (AsyncClamAVGRPCClient).

The grpc.aio channel must be created on the same event loop as the test,
so we spin up a synchronous gRPC server and create the async client
fresh inside each test.
"""

from __future__ import annotations

from concurrent import futures

import grpc
import pytest

from clamav_sdk._proto import clamav_pb2_grpc
from clamav_sdk.async_grpc_client import AsyncClamAVGRPCClient
from clamav_sdk.exceptions import ClamAVBadRequestError

from .test_grpc_client import FakeClamAVServicer


@pytest.fixture(scope="module")
def grpc_server():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    clamav_pb2_grpc.add_ClamAVScannerServicer_to_server(FakeClamAVServicer(), server)
    port = server.add_insecure_port("[::]:0")
    server.start()
    yield f"localhost:{port}"
    server.stop(grace=0)


class TestHealthCheck:
    async def test_healthy(self, grpc_server: str):
        async with AsyncClamAVGRPCClient(target=grpc_server) as client:
            result = await client.health_check()
            assert result.healthy is True


class TestScanFile:
    async def test_clean(self, grpc_server: str, sample_bytes: bytes):
        async with AsyncClamAVGRPCClient(target=grpc_server) as client:
            result = await client.scan_file(sample_bytes, filename="async.txt")
            assert result.status == "OK"
            assert result.filename == "async.txt"

    async def test_virus(self, grpc_server: str, eicar_bytes: bytes):
        async with AsyncClamAVGRPCClient(target=grpc_server) as client:
            result = await client.scan_file(eicar_bytes, filename="eicar.com")
            assert result.status == "FOUND"

    async def test_empty(self, grpc_server: str):
        async with AsyncClamAVGRPCClient(target=grpc_server) as client:
            with pytest.raises(ClamAVBadRequestError):
                await client.scan_file(b"")


class TestScanStream:
    async def test_clean(self, grpc_server: str, sample_bytes: bytes):
        async with AsyncClamAVGRPCClient(target=grpc_server) as client:
            result = await client.scan_stream(sample_bytes, filename="stream.txt", chunk_size=4)
            assert result.status == "OK"


class TestScanMultiple:
    async def test_mixed(self, grpc_server: str, sample_bytes: bytes, eicar_bytes: bytes):
        async with AsyncClamAVGRPCClient(target=grpc_server) as client:
            files = [
                ("clean.txt", sample_bytes),
                ("eicar.com", eicar_bytes),
            ]
            results = []
            async for r in client.scan_multiple(files, chunk_size=16):
                results.append(r)
            assert len(results) == 2
            assert results[0].status == "OK"
            assert results[1].status == "FOUND"


class TestContextManager:
    async def test_aenter_aexit(self, grpc_server: str):
        async with AsyncClamAVGRPCClient(target=grpc_server) as c:
            result = await c.health_check()
            assert result.healthy is True
