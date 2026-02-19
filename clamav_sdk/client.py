"""Synchronous REST client for the ClamAV API."""

from __future__ import annotations

import os
from pathlib import Path
from typing import BinaryIO, Union

import requests

from clamav_sdk.exceptions import (
    ClamAVBadRequestError,
    ClamAVConnectionError,
    ClamAVFileTooLargeError,
    ClamAVServiceUnavailableError,
    ClamAVTimeoutError,
)
from clamav_sdk.models import HealthCheckResult, ScanResult, VersionInfo


class ClamAVClient:
    """Synchronous client for the ClamAV REST API.

    Args:
        base_url: Root URL of the ClamAV API server.
        timeout: Default request timeout in seconds.
        session: Optional pre-configured :class:`requests.Session` for
            connection pooling or custom authentication headers.

    Example::

        client = ClamAVClient("http://localhost:6000")
        result = client.scan_file("/tmp/sample.txt")
        print(result.status)
    """

    def __init__(
        self,
        base_url: str = "http://localhost:6000",
        timeout: float = 300,
        session: requests.Session | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = session or requests.Session()

    def health_check(self) -> HealthCheckResult:
        """Check whether the ClamAV service is healthy.

        Returns:
            A :class:`HealthCheckResult` with the service status.

        Raises:
            ClamAVServiceUnavailableError: If the ClamAV daemon is down.
            ClamAVConnectionError: If the server is unreachable.
        """
        data = self._get("/api/health-check")
        return HealthCheckResult(
            healthy=data.get("message") == "ok",
            message=data.get("message", ""),
        )

    def version(self) -> VersionInfo:
        """Retrieve the ClamAV API server build metadata.

        Returns:
            A :class:`VersionInfo` with version, commit, and build timestamp.

        Raises:
            ClamAVConnectionError: If the server is unreachable.
        """
        data = self._get("/api/version")
        return VersionInfo(
            version=data.get("version", ""),
            commit=data.get("commit", ""),
            build=data.get("build", ""),
        )

    def scan_file(self, file_path: Union[str, Path]) -> ScanResult:
        """Scan a file on disk via multipart upload.

        Args:
            file_path: Path to the file to scan.

        Returns:
            A :class:`ScanResult` with the scan outcome.

        Raises:
            FileNotFoundError: If *file_path* does not exist.
            ClamAVFileTooLargeError: If the file exceeds the server limit.
            ClamAVTimeoutError: If the scan times out.
            ClamAVServiceUnavailableError: If the ClamAV daemon is down.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        with open(path, "rb") as fh:
            return self._post_multipart("/api/scan", fh, path.name)

    def scan_bytes(self, data: bytes, filename: str = "file") -> ScanResult:
        """Scan in-memory bytes via multipart upload.

        Args:
            data: Raw file content.
            filename: Filename hint sent to the server.

        Returns:
            A :class:`ScanResult` with the scan outcome.
        """
        import io

        return self._post_multipart("/api/scan", io.BytesIO(data), filename)

    def scan_stream(self, data: Union[bytes, BinaryIO]) -> ScanResult:
        """Scan data via the binary stream endpoint.

        Sends the payload as ``application/octet-stream`` to ``/api/stream-scan``
        with an explicit ``Content-Length`` header.

        Args:
            data: Raw bytes or a readable binary stream.

        Returns:
            A :class:`ScanResult` with the scan outcome.
        """
        if isinstance(data, bytes):
            content_length = len(data)
            body: Union[bytes, BinaryIO] = data
        else:
            pos = data.tell()
            data.seek(0, os.SEEK_END)
            content_length = data.tell() - pos
            data.seek(pos)
            body = data

        headers = {
            "Content-Type": "application/octet-stream",
            "Content-Length": str(content_length),
        }
        return self._post_stream("/api/stream-scan", body, headers)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(self, path: str) -> dict:
        try:
            resp = self._session.get(
                f"{self._base_url}{path}",
                timeout=self._timeout,
            )
        except requests.ConnectionError as exc:
            raise ClamAVConnectionError(str(exc)) from exc
        except requests.Timeout as exc:
            raise ClamAVTimeoutError(str(exc)) from exc

        self._raise_for_status(resp)
        return resp.json()  # type: ignore[no-any-return]

    def _post_multipart(self, path: str, fileobj: BinaryIO, filename: str) -> ScanResult:
        try:
            resp = self._session.post(
                f"{self._base_url}{path}",
                files={"file": (filename, fileobj)},
                timeout=self._timeout,
            )
        except requests.ConnectionError as exc:
            raise ClamAVConnectionError(str(exc)) from exc
        except requests.Timeout as exc:
            raise ClamAVTimeoutError(str(exc)) from exc

        self._raise_for_status(resp)
        return self._parse_scan_response(resp.json())

    def _post_stream(self, path: str, body: Union[bytes, BinaryIO], headers: dict) -> ScanResult:
        try:
            resp = self._session.post(
                f"{self._base_url}{path}",
                data=body,
                headers=headers,
                timeout=self._timeout,
            )
        except requests.ConnectionError as exc:
            raise ClamAVConnectionError(str(exc)) from exc
        except requests.Timeout as exc:
            raise ClamAVTimeoutError(str(exc)) from exc

        self._raise_for_status(resp)
        return self._parse_scan_response(resp.json())

    def _raise_for_status(self, resp: requests.Response) -> None:
        if resp.status_code == 200:
            return
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
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
