"""Shared test fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture()
def sample_bytes() -> bytes:
    return b"Hello, ClamAV!"


@pytest.fixture()
def eicar_bytes() -> bytes:
    """EICAR anti-malware test string (safe; every AV recognises it)."""
    return b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
