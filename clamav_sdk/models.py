"""Data models for ClamAV SDK responses."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScanResult:
    """Result of a file or stream scan operation.

    Attributes:
        status: Scan outcome — ``"OK"``, ``"FOUND"``, or ``"ERROR"``.
        message: Virus signature name, error description, or empty string.
        scan_time: Wall-clock scan duration in seconds.
        filename: Original filename (echoed by gRPC; empty for REST).
    """

    status: str
    message: str
    scan_time: float
    filename: str = ""


@dataclass(frozen=True, slots=True)
class HealthCheckResult:
    """Health status of the ClamAV service.

    Attributes:
        healthy: ``True`` when the service and ClamAV daemon are operational.
        message: Human-readable status description.
    """

    healthy: bool
    message: str


@dataclass(frozen=True, slots=True)
class VersionInfo:
    """Build metadata of the ClamAV API server.

    Attributes:
        version: Semantic version string (e.g. ``"1.3.0"``).
        commit: Short Git commit hash of the build.
        build: ISO-8601 build timestamp.
    """

    version: str
    commit: str
    build: str
