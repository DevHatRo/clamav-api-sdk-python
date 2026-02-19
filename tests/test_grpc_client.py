"""Tests for the synchronous gRPC client (ClamAVGRPCClient).

Uses an in-process gRPC server with a fake ClamAVScanner servicer.
"""

from __future__ import annotations

import io
from concurrent import futures

import grpc
import pytest

from clamav_sdk._proto import clamav_pb2, clamav_pb2_grpc
from clamav_sdk.exceptions import (
    ClamAVBadRequestError,
    ClamAVConnectionError,
    ClamAVFileTooLargeError,
    ClamAVServiceUnavailableError,
    ClamAVTimeoutError,
)
from clamav_sdk.grpc_client import ClamAVGRPCClient


# ------------------------------------------------------------------ #
# Fake servicer
# ------------------------------------------------------------------ #


class FakeClamAVServicer(clamav_pb2_grpc.ClamAVScannerServicer):
    """In-process fake that mimics the real ClamAV gRPC service."""

    def HealthCheck(self, request, context):
        return clamav_pb2.HealthCheckResponse(status="healthy", message="ok")

    def ScanFile(self, request, context):
        if not request.data:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("empty file data")
            return clamav_pb2.ScanResponse()
        if len(request.data) > 10_000_000:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("file too large")
            return clamav_pb2.ScanResponse()
        if b"EICAR" in request.data:
            return clamav_pb2.ScanResponse(
                status="FOUND",
                message="Eicar-Test-Signature",
                scan_time=0.002,
                filename=request.filename,
            )
        return clamav_pb2.ScanResponse(
            status="OK",
            message="",
            scan_time=0.001,
            filename=request.filename,
        )

    def ScanStream(self, request_iterator, context):
        data = b""
        filename = ""
        for req in request_iterator:
            data += req.chunk
            if req.filename:
                filename = req.filename
        if b"EICAR" in data:
            return clamav_pb2.ScanResponse(
                status="FOUND", message="Eicar-Test-Signature", scan_time=0.002, filename=filename
            )
        return clamav_pb2.ScanResponse(status="OK", message="", scan_time=0.001, filename=filename)

    def ScanMultiple(self, request_iterator, context):
        files: list[tuple[str, bytes]] = []
        current_data = b""
        current_name = ""
        for req in request_iterator:
            if req.filename:
                current_name = req.filename
            current_data += req.chunk
            if req.is_last:
                files.append((current_name, current_data))
                current_data = b""
                current_name = ""

        for fname, fdata in files:
            if b"EICAR" in fdata:
                yield clamav_pb2.ScanResponse(
                    status="FOUND", message="Eicar-Test-Signature", scan_time=0.002, filename=fname
                )
            else:
                yield clamav_pb2.ScanResponse(status="OK", message="", scan_time=0.001, filename=fname)


# ------------------------------------------------------------------ #
# Fixtures
# ------------------------------------------------------------------ #


@pytest.fixture(scope="module")
def grpc_server():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    clamav_pb2_grpc.add_ClamAVScannerServicer_to_server(FakeClamAVServicer(), server)
    port = server.add_insecure_port("[::]:0")
    server.start()
    yield f"localhost:{port}"
    server.stop(grace=0)


@pytest.fixture()
def client(grpc_server: str) -> ClamAVGRPCClient:
    c = ClamAVGRPCClient(target=grpc_server)
    yield c  # type: ignore[misc]
    c.close()


# ------------------------------------------------------------------ #
# Tests
# ------------------------------------------------------------------ #


class TestHealthCheck:
    def test_healthy(self, client: ClamAVGRPCClient):
        result = client.health_check()
        assert result.healthy is True
        assert result.message == "ok"


class TestScanFile:
    def test_clean(self, client: ClamAVGRPCClient, sample_bytes: bytes):
        result = client.scan_file(sample_bytes, filename="clean.txt")
        assert result.status == "OK"
        assert result.filename == "clean.txt"

    def test_virus(self, client: ClamAVGRPCClient, eicar_bytes: bytes):
        result = client.scan_file(eicar_bytes, filename="eicar.com")
        assert result.status == "FOUND"
        assert result.message == "Eicar-Test-Signature"
        assert result.filename == "eicar.com"

    def test_empty_data(self, client: ClamAVGRPCClient):
        with pytest.raises(ClamAVBadRequestError):
            client.scan_file(b"")


class TestScanStream:
    def test_clean(self, client: ClamAVGRPCClient, sample_bytes: bytes):
        result = client.scan_stream(sample_bytes, filename="stream.txt", chunk_size=4)
        assert result.status == "OK"
        assert result.filename == "stream.txt"

    def test_binary_io(self, client: ClamAVGRPCClient, sample_bytes: bytes):
        result = client.scan_stream(io.BytesIO(sample_bytes), filename="bio.txt")
        assert result.status == "OK"

    def test_virus(self, client: ClamAVGRPCClient, eicar_bytes: bytes):
        result = client.scan_stream(eicar_bytes, filename="eicar.com", chunk_size=16)
        assert result.status == "FOUND"


class TestScanMultiple:
    def test_mixed(self, client: ClamAVGRPCClient, sample_bytes: bytes, eicar_bytes: bytes):
        files = [
            ("clean.txt", sample_bytes),
            ("eicar.com", eicar_bytes),
            ("also_clean.txt", b"safe data"),
        ]
        results = client.scan_multiple(files, chunk_size=16)
        assert len(results) == 3
        assert results[0].status == "OK"
        assert results[0].filename == "clean.txt"
        assert results[1].status == "FOUND"
        assert results[1].filename == "eicar.com"
        assert results[2].status == "OK"


class TestContextManager:
    def test_enter_exit(self, grpc_server: str):
        with ClamAVGRPCClient(target=grpc_server) as c:
            result = c.health_check()
            assert result.healthy is True


class TestConnectionError:
    def test_unreachable(self):
        c = ClamAVGRPCClient(target="localhost:1")
        with pytest.raises((ClamAVConnectionError, Exception)):
            c.health_check()
        c.close()
