"""Tests for clamav_sdk.models."""

import pytest

from clamav_sdk.models import HealthCheckResult, ScanResult, VersionInfo


class TestScanResult:
    def test_defaults(self):
        r = ScanResult(status="OK", message="", scan_time=0.001)
        assert r.filename == ""

    def test_all_fields(self):
        r = ScanResult(status="FOUND", message="Eicar", scan_time=0.5, filename="test.bin")
        assert r.status == "FOUND"
        assert r.message == "Eicar"
        assert r.scan_time == 0.5
        assert r.filename == "test.bin"

    def test_frozen(self):
        r = ScanResult(status="OK", message="", scan_time=0.0)
        with pytest.raises(AttributeError):
            r.status = "FOUND"  # type: ignore[misc]


class TestHealthCheckResult:
    def test_healthy(self):
        r = HealthCheckResult(healthy=True, message="ok")
        assert r.healthy is True

    def test_unhealthy(self):
        r = HealthCheckResult(healthy=False, message="Clamd service unavailable")
        assert r.healthy is False


class TestVersionInfo:
    def test_fields(self):
        v = VersionInfo(version="1.3.0", commit="abc1234", build="2025-10-16T12:00:00Z")
        assert v.version == "1.3.0"
        assert v.commit == "abc1234"
        assert v.build == "2025-10-16T12:00:00Z"
