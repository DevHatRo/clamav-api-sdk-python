"""Asynchronous REST client for the ClamAV API (requires ``httpx``)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import BinaryIO, Union

import httpx

from clamav_sdk.exceptions import (
    ClamAVBadRequestError,
    ClamAVConnectionError,
    ClamAVFileTooLargeError,
    ClamAVServiceUnavailableError,
    ClamAVTimeoutError,
)
from clamav_sdk.models import HealthCheckResult, ScanResult, VersionInfo


class AsyncClamAVClient:
    """Asynchronous client for the ClamAV REST API.

    Requires the ``httpx`` package (install with ``pip install clamav-sdk[async]``).

    Args:
        base_url: Root URL of the ClamAV API server.
        timeout: Default request timeout in seconds.
        client: Optional pre-configured :class:`httpx.AsyncClient`.

    Example::

        async with AsyncClamAVClient("http://localhost:6000") as client:
            result = await client.scan_file("/tmp/sample.txt")
            print(result.status)
    """

    def __init__(
        self,
        base_url: str = "http://localhost:6000",
        timeout: float = 300,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout)

    async def health_check(self) -> HealthCheckResult:
        """Check whether the ClamAV service is healthy.

        Returns:
            A :class:`HealthCheckResult` with the service status.
        """
        data = await self._get("/api/health-check")
        return HealthCheckResult(
            healthy=data.get("message") == "ok",
            message=data.get("message", ""),
        )

    async def version(self) -> VersionInfo:
        """Retrieve the ClamAV API server build metadata.

        Returns:
            A :class:`VersionInfo` with version, commit, and build timestamp.
        """
        data = await self._get("/api/version")
        return VersionInfo(
            version=data.get("version", ""),
            commit=data.get("commit", ""),
            build=data.get("build", ""),
        )

    async def scan_file(self, file_path: Union[str, Path]) -> ScanResult:
        """Scan a file on disk via multipart upload.

        Args:
            file_path: Path to the file to scan.

        Returns:
            A :class:`ScanResult` with the scan outcome.

        Raises:
            FileNotFoundError: If *file_path* does not exist.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        with open(path, "rb") as fh:
            content = fh.read()
        return await self._post_multipart("/api/scan", content, path.name)

    async def scan_bytes(self, data: bytes, filename: str = "file") -> ScanResult:
        """Scan in-memory bytes via multipart upload.

        Args:
            data: Raw file content.
            filename: Filename hint sent to the server.

        Returns:
            A :class:`ScanResult` with the scan outcome.
        """
        return await self._post_multipart("/api/scan", data, filename)

    async def scan_stream(self, data: Union[bytes, BinaryIO]) -> ScanResult:
        """Scan data via the binary stream endpoint.

        Args:
            data: Raw bytes or a readable binary stream.

        Returns:
            A :class:`ScanResult` with the scan outcome.
        """
        if isinstance(data, bytes):
            content_length = len(data)
            body = data
        else:
            pos = data.tell()
            data.seek(0, os.SEEK_END)
            content_length = data.tell() - pos
            data.seek(pos)
            body = data.read()

        headers = {
            "Content-Type": "application/octet-stream",
            "Content-Length": str(content_length),
        }
        return await self._post_stream("/api/stream-scan", body, headers)

    async def close(self) -> None:
        """Close the underlying HTTP client if owned by this instance."""
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> AsyncClamAVClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get(self, path: str) -> dict:
        try:
            resp = await self._client.get(f"{self._base_url}{path}", timeout=self._timeout)
        except httpx.ConnectError as exc:
            raise ClamAVConnectionError(str(exc)) from exc
        except httpx.TimeoutException as exc:
            raise ClamAVTimeoutError(str(exc)) from exc

        self._raise_for_status(resp)
        return resp.json()  # type: ignore[no-any-return]

    async def _post_multipart(self, path: str, data: bytes, filename: str) -> ScanResult:
        try:
            resp = await self._client.post(
                f"{self._base_url}{path}",
                files={"file": (filename, data)},
                timeout=self._timeout,
            )
        except httpx.ConnectError as exc:
            raise ClamAVConnectionError(str(exc)) from exc
        except httpx.TimeoutException as exc:
            raise ClamAVTimeoutError(str(exc)) from exc

        self._raise_for_status(resp)
        return self._parse_scan_response(resp.json())

    async def _post_stream(self, path: str, body: bytes, headers: dict) -> ScanResult:
        try:
            resp = await self._client.post(
                f"{self._base_url}{path}",
                content=body,
                headers=headers,
                timeout=self._timeout,
            )
        except httpx.ConnectError as exc:
            raise ClamAVConnectionError(str(exc)) from exc
        except httpx.TimeoutException as exc:
            raise ClamAVTimeoutError(str(exc)) from exc

        self._raise_for_status(resp)
        return self._parse_scan_response(resp.json())

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        if resp.status_code == 200:
            return
        try:
            body = resp.json()
        except Exception:
            body = {}
        msg = body.get("message", resp.text)
        if resp.status_code == 400:
            raise ClamAVBadRequestError(msg)
        if resp.status_code == 413:
            raise ClamAVFileTooLargeError(msg)
        if resp.status_code == 502:
            raise ClamAVServiceUnavailableError(msg)
        if resp.status_code == 504:
            raise ClamAVTimeoutError(msg)
        resp.raise_for_status()

    @staticmethod
    def _parse_scan_response(data: dict) -> ScanResult:
        return ScanResult(
            status=data.get("status", "ERROR"),
            message=data.get("message", ""),
            scan_time=data.get("time", 0.0),
        )
