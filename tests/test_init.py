"""Tests for clamav_sdk.__init__ lazy imports and exports."""

import clamav_sdk


def test_lazy_import_async_client():
    cls = clamav_sdk.AsyncClamAVClient
    assert cls.__name__ == "AsyncClamAVClient"


def test_lazy_import_async_grpc_client():
    cls = clamav_sdk.AsyncClamAVGRPCClient
    assert cls.__name__ == "AsyncClamAVGRPCClient"


def test_lazy_import_unknown_raises():
    import pytest

    with pytest.raises(AttributeError, match="has no attribute"):
        _ = clamav_sdk.NoSuchThing  # type: ignore[attr-defined]


def test_all_exports():
    for name in clamav_sdk.__all__:
        assert hasattr(clamav_sdk, name)
