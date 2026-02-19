"""Asynchronous gRPC client for the ClamAV Scanner service."""

from __future__ import annotations

import io
from collections.abc import AsyncIterator
from typing import BinaryIO

import grpc
import grpc.aio

from clamav_sdk._proto import clamav_pb2, clamav_pb2_grpc
from clamav_sdk.grpc_client import _handle_rpc_error, _to_scan_result
from clamav_sdk.models import HealthCheckResult, ScanResult

_MAX_MSG = 200 * 1024 * 1024  # 200 MiB default


class AsyncClamAVGRPCClient:
    """Asynchronous gRPC client for the ClamAV Scanner service.

    Args:
        target: gRPC server address (``host:port``).
        credentials: Optional TLS channel credentials.  When *None* an
            insecure channel is created.
        max_message_size: Maximum send/receive message size in bytes.

    Example::

        async with AsyncClamAVGRPCClient("localhost:9000") as client:
            result = await client.scan_file(payload)
            print(result.status)
    """

    def __init__(
        self,
        target: str = "localhost:9000",
        credentials: grpc.ChannelCredentials | None = None,
        max_message_size: int = _MAX_MSG,
    ) -> None:
        options = [
            ("grpc.max_send_message_length", max_message_size),
            ("grpc.max_receive_message_length", max_message_size),
        ]
        if credentials is not None:
            self._channel: grpc.aio.Channel = grpc.aio.secure_channel(target, credentials, options=options)
        else:
            self._channel = grpc.aio.insecure_channel(target, options=options)
        self._stub = clamav_pb2_grpc.ClamAVScannerStub(self._channel)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def health_check(self) -> HealthCheckResult:
        """Check the health of the ClamAV service.

        Returns:
            A :class:`HealthCheckResult` describing service health.
        """
        try:
            resp = await self._stub.HealthCheck(clamav_pb2.HealthCheckRequest())
        except grpc.aio.AioRpcError as exc:
            _handle_rpc_error(exc)
            raise

        return HealthCheckResult(
            healthy=resp.status == "healthy",
            message=resp.message,
        )

    async def scan_file(self, data: bytes, filename: str = "") -> ScanResult:
        """Scan a complete file payload in a single unary RPC.

        Args:
            data: Raw file bytes.
            filename: Optional filename hint.

        Returns:
            A :class:`ScanResult` with the scan outcome.
        """
        req = clamav_pb2.ScanFileRequest(data=data, filename=filename)
        try:
            resp = await self._stub.ScanFile(req)
        except grpc.aio.AioRpcError as exc:
            _handle_rpc_error(exc)
            raise

        return _to_scan_result(resp)

    async def scan_stream(
        self,
        data: bytes | BinaryIO,
        filename: str = "",
        chunk_size: int = 65536,
    ) -> ScanResult:
        """Scan data using the client-streaming RPC.

        Args:
            data: Raw bytes or a readable binary stream.
            filename: Optional filename sent with the first chunk.
            chunk_size: Size of each chunk in bytes.

        Returns:
            A :class:`ScanResult` with the scan outcome.
        """
        try:
            resp = await self._stub.ScanStream(_async_chunk_iter(data, filename, chunk_size))
        except grpc.aio.AioRpcError as exc:
            _handle_rpc_error(exc)
            raise

        return _to_scan_result(resp)

    async def scan_multiple(
        self,
        files: list[tuple[str, bytes | BinaryIO]],
        chunk_size: int = 65536,
    ) -> AsyncIterator[ScanResult]:
        """Scan multiple files over a single bidirectional stream.

        Yields :class:`ScanResult` objects as they arrive from the server.

        Args:
            files: List of ``(filename, data)`` tuples.
            chunk_size: Size of each chunk in bytes.

        Yields:
            :class:`ScanResult` for each scanned file.
        """

        async def request_iter() -> AsyncIterator[clamav_pb2.ScanStreamRequest]:
            for fname, fdata in files:
                async for msg in _async_chunk_iter(fdata, fname, chunk_size):
                    yield msg

        try:
            call = self._stub.ScanMultiple(request_iter())
            async for resp in call:
                yield _to_scan_result(resp)
        except grpc.aio.AioRpcError as exc:
            _handle_rpc_error(exc)
            raise

    async def close(self) -> None:
        """Shut down the underlying gRPC channel."""
        await self._channel.close()

    async def __aenter__(self) -> AsyncClamAVGRPCClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


async def _async_chunk_iter(
    data: bytes | BinaryIO,
    filename: str,
    chunk_size: int,
) -> AsyncIterator[clamav_pb2.ScanStreamRequest]:
    """Yield ``ScanStreamRequest`` messages for a single file (async generator)."""
    stream: BinaryIO = io.BytesIO(data) if isinstance(data, bytes) else data
    chunks: list[bytes] = []
    while True:
        piece = stream.read(chunk_size)
        if not piece:
            break
        chunks.append(piece)

    for idx, chunk in enumerate(chunks):
        is_last = idx == len(chunks) - 1
        yield clamav_pb2.ScanStreamRequest(
            chunk=chunk,
            filename=filename if idx == 0 else "",
            is_last=is_last,
        )
