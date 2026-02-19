"""Synchronous gRPC client for the ClamAV Scanner service."""

from __future__ import annotations

import io
from typing import BinaryIO, Iterator, Union

import grpc

from clamav_sdk._proto import clamav_pb2, clamav_pb2_grpc
from clamav_sdk.exceptions import (
    ClamAVBadRequestError,
    ClamAVConnectionError,
    ClamAVError,
    ClamAVFileTooLargeError,
    ClamAVServiceUnavailableError,
    ClamAVTimeoutError,
)
from clamav_sdk.models import HealthCheckResult, ScanResult

_MAX_MSG = 200 * 1024 * 1024  # 200 MiB default


class ClamAVGRPCClient:
    """Synchronous gRPC client for the ClamAV Scanner service.

    Args:
        target: gRPC server address (``host:port``).
        credentials: Optional TLS channel credentials.  When *None* an
            insecure channel is created.
        max_message_size: Maximum send/receive message size in bytes.

    Example::

        with ClamAVGRPCClient("localhost:9000") as client:
            result = client.scan_file(open("sample.bin", "rb").read())
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
            self._channel = grpc.secure_channel(target, credentials, options=options)
        else:
            self._channel = grpc.insecure_channel(target, options=options)
        self._stub = clamav_pb2_grpc.ClamAVScannerStub(self._channel)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def health_check(self) -> HealthCheckResult:
        """Check the health of the ClamAV service.

        Returns:
            A :class:`HealthCheckResult` describing service health.
        """
        try:
            resp = self._stub.HealthCheck(clamav_pb2.HealthCheckRequest())
        except grpc.RpcError as exc:
            _handle_rpc_error(exc)
            raise  # unreachable, keeps type-checkers happy

        return HealthCheckResult(
            healthy=resp.status == "healthy",
            message=resp.message,
        )

    def scan_file(self, data: bytes, filename: str = "") -> ScanResult:
        """Scan a complete file payload in a single unary RPC.

        Args:
            data: Raw file bytes.
            filename: Optional filename hint.

        Returns:
            A :class:`ScanResult` with the scan outcome.
        """
        req = clamav_pb2.ScanFileRequest(data=data, filename=filename)
        try:
            resp = self._stub.ScanFile(req)
        except grpc.RpcError as exc:
            _handle_rpc_error(exc)
            raise

        return _to_scan_result(resp)

    def scan_stream(
        self,
        data: Union[bytes, BinaryIO],
        filename: str = "",
        chunk_size: int = 65536,
    ) -> ScanResult:
        """Scan data using the client-streaming RPC.

        The payload is split into chunks of *chunk_size* bytes and sent as
        a stream of ``ScanStreamRequest`` messages.

        Args:
            data: Raw bytes or a readable binary stream.
            filename: Optional filename sent with the first chunk.
            chunk_size: Size of each chunk in bytes.

        Returns:
            A :class:`ScanResult` with the scan outcome.
        """
        try:
            resp = self._stub.ScanStream(_chunk_iter(data, filename, chunk_size))
        except grpc.RpcError as exc:
            _handle_rpc_error(exc)
            raise

        return _to_scan_result(resp)

    def scan_multiple(
        self,
        files: list[tuple[str, Union[bytes, BinaryIO]]],
        chunk_size: int = 65536,
    ) -> list[ScanResult]:
        """Scan multiple files over a single bidirectional stream.

        Per-file errors are reported inside the returned :class:`ScanResult`
        objects (with ``status="ERROR"``), not as RPC errors, so the stream
        stays open for remaining files.

        Args:
            files: List of ``(filename, data)`` tuples.
            chunk_size: Size of each chunk in bytes.

        Returns:
            A list of :class:`ScanResult` in the same order as *files*.
        """

        def request_iter() -> Iterator[clamav_pb2.ScanStreamRequest]:
            for fname, fdata in files:
                yield from _chunk_iter(fdata, fname, chunk_size)

        try:
            responses = self._stub.ScanMultiple(request_iter())
            return [_to_scan_result(r) for r in responses]
        except grpc.RpcError as exc:
            _handle_rpc_error(exc)
            raise

    def close(self) -> None:
        """Shut down the underlying gRPC channel."""
        self._channel.close()

    def __enter__(self) -> ClamAVGRPCClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


# ------------------------------------------------------------------
# Module-level helpers (shared with async variant)
# ------------------------------------------------------------------


def _chunk_iter(
    data: Union[bytes, BinaryIO],
    filename: str,
    chunk_size: int,
) -> Iterator[clamav_pb2.ScanStreamRequest]:
    """Yield ``ScanStreamRequest`` messages for a single file."""
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


def _to_scan_result(resp: clamav_pb2.ScanResponse) -> ScanResult:
    return ScanResult(
        status=resp.status,
        message=resp.message,
        scan_time=resp.scan_time,
        filename=resp.filename,
    )


def _handle_rpc_error(exc: grpc.RpcError) -> None:
    code = exc.code()  # type: ignore[union-attr]
    details = exc.details() or ""  # type: ignore[union-attr]

    if code == grpc.StatusCode.UNAVAILABLE:
        raise ClamAVConnectionError(details) from exc
    if code == grpc.StatusCode.DEADLINE_EXCEEDED:
        raise ClamAVTimeoutError(details) from exc
    if code == grpc.StatusCode.INTERNAL:
        raise ClamAVServiceUnavailableError(details) from exc
    if code == grpc.StatusCode.INVALID_ARGUMENT:
        if "too large" in details.lower():
            raise ClamAVFileTooLargeError(details) from exc
        raise ClamAVBadRequestError(details) from exc
    if code == grpc.StatusCode.CANCELLED:
        raise ClamAVError(details) from exc
    raise ClamAVError(f"gRPC error {code}: {details}") from exc
