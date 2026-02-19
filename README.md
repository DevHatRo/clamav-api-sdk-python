# clamav-sdk

Python SDK for the [ClamAV API](https://github.com/DevHatRo/ClamAV-API) service. Supports both REST (HTTP/JSON) and gRPC transports with synchronous and asynchronous interfaces.

## Installation

```bash
pip install clamav-sdk
```

For async REST support (uses [httpx](https://www.python-httpx.org/)):

```bash
pip install clamav-sdk[async]
```

## Quick Start — REST Client

```python
from clamav_sdk import ClamAVClient

client = ClamAVClient("http://localhost:6000")

# Health check
health = client.health_check()
print(health.healthy, health.message)

# Server version
info = client.version()
print(f"{info.version} ({info.commit})")

# Scan a file on disk
result = client.scan_file("/path/to/file.pdf")
print(result.status, result.message, result.scan_time)

# Scan in-memory bytes
result = client.scan_bytes(b"file content", filename="doc.txt")

# Scan via binary stream endpoint
result = client.scan_stream(b"raw bytes")
```

## Quick Start — gRPC Client

```python
from clamav_sdk import ClamAVGRPCClient

with ClamAVGRPCClient("localhost:9000") as client:
    # Health check
    health = client.health_check()

    # Scan file bytes (unary RPC)
    result = client.scan_file(open("sample.bin", "rb").read(), filename="sample.bin")
    print(result.status)

    # Scan via streaming RPC (automatic chunking)
    result = client.scan_stream(large_payload, filename="big.zip", chunk_size=65536)

    # Scan multiple files over a single bidirectional stream
    files = [
        ("report.pdf", open("report.pdf", "rb")),
        ("image.png", open("image.png", "rb")),
    ]
    results = client.scan_multiple(files)
    for r in results:
        print(f"{r.filename}: {r.status}")
```

## Async REST Client

Requires the `async` extra (`pip install clamav-sdk[async]`).

```python
import asyncio
from clamav_sdk import AsyncClamAVClient

async def main():
    async with AsyncClamAVClient("http://localhost:6000") as client:
        health = await client.health_check()
        result = await client.scan_file("/path/to/file.pdf")
        print(result.status)

asyncio.run(main())
```

## Async gRPC Client

```python
import asyncio
from clamav_sdk import AsyncClamAVGRPCClient

async def main():
    async with AsyncClamAVGRPCClient("localhost:9000") as client:
        result = await client.scan_file(b"payload", filename="test.bin")
        print(result.status)

        # scan_multiple yields results as they arrive
        files = [("a.txt", b"aaa"), ("b.txt", b"bbb")]
        async for r in client.scan_multiple(files):
            print(f"{r.filename}: {r.status}")

asyncio.run(main())
```

## TLS / Secure Channels

```python
import grpc
from clamav_sdk import ClamAVGRPCClient

creds = grpc.ssl_channel_credentials(
    root_certificates=open("ca.pem", "rb").read(),
)
client = ClamAVGRPCClient("secure-host:9000", credentials=creds)
```

## Custom Session / Authentication

```python
import requests
from clamav_sdk import ClamAVClient

session = requests.Session()
session.headers["Authorization"] = "Bearer <token>"
client = ClamAVClient("http://localhost:6000", session=session)
```

## Exception Handling

All SDK methods raise exceptions from a unified hierarchy:

```python
from clamav_sdk import ClamAVClient
from clamav_sdk.exceptions import (
    ClamAVError,                    # base
    ClamAVConnectionError,          # server unreachable
    ClamAVTimeoutError,             # scan timed out (HTTP 504 / gRPC DEADLINE_EXCEEDED)
    ClamAVServiceUnavailableError,  # ClamAV daemon down (HTTP 502 / gRPC INTERNAL)
    ClamAVFileTooLargeError,        # file exceeds size limit (HTTP 413)
    ClamAVBadRequestError,          # malformed request (HTTP 400)
)

client = ClamAVClient("http://localhost:6000")
try:
    result = client.scan_file("huge.iso")
except ClamAVFileTooLargeError:
    print("File exceeds server limit")
except ClamAVTimeoutError:
    print("Scan took too long")
except ClamAVError as exc:
    print(f"Unexpected error: {exc}")
```

## Models

| Model | Fields |
|---|---|
| `ScanResult` | `status`, `message`, `scan_time`, `filename` |
| `HealthCheckResult` | `healthy`, `message` |
| `VersionInfo` | `version`, `commit`, `build` |

## Development

```bash
git clone https://github.com/DevHatRo/clamav-api-sdk-python.git
cd clamav-api-sdk-python
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest --cov=clamav_sdk
```

## License

[MIT](LICENSE)
