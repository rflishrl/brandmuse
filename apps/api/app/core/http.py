import httpx

_shared_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    """Return persistent singleton httpx.AsyncClient with connection pooling.

    Reusing this client avoids repeated TCP/TLS handshakes, saves file descriptors,
    and drastically reduces latency and memory churn across outgoing HTTP requests.
    """
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        limits = httpx.Limits(
            max_keepalive_connections=20,
            max_connections=50,
            keepalive_expiry=30.0,
        )
        _shared_client = httpx.AsyncClient(
            limits=limits,
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=True,
        )
    return _shared_client


async def close_http_client() -> None:
    """Gracefully close persistent HTTP connection pool on application shutdown."""
    global _shared_client
    if _shared_client is not None and not _shared_client.is_closed:
        await _shared_client.aclose()
        _shared_client = None
