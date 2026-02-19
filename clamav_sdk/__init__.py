"""ClamAV SDK — Python client for the ClamAV API (REST and gRPC)."""

from clamav_sdk.client import ClamAVClient
from clamav_sdk.exceptions import (
    ClamAVBadRequestError,
    ClamAVConnectionError,
    ClamAVError,
    ClamAVFileTooLargeError,
    ClamAVServiceUnavailableError,
    ClamAVTimeoutError,
)
from clamav_sdk.grpc_client import ClamAVGRPCClient
from clamav_sdk.models import HealthCheckResult, ScanResult, VersionInfo

__all__ = [
    "ClamAVClient",
    "ClamAVGRPCClient",
    "AsyncClamAVClient",
    "AsyncClamAVGRPCClient",
    "ScanResult",
    "HealthCheckResult",
    "VersionInfo",
    "ClamAVError",
    "ClamAVConnectionError",
    "ClamAVTimeoutError",
    "ClamAVServiceUnavailableError",
    "ClamAVFileTooLargeError",
    "ClamAVBadRequestError",
]


def __getattr__(name: str) -> object:
    """Lazy-import async clients so ``httpx`` / ``grpc.aio`` are optional at import time."""
    if name == "AsyncClamAVClient":
        from clamav_sdk.async_client import AsyncClamAVClient

        return AsyncClamAVClient
    if name == "AsyncClamAVGRPCClient":
        from clamav_sdk.async_grpc_client import AsyncClamAVGRPCClient

        return AsyncClamAVGRPCClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
