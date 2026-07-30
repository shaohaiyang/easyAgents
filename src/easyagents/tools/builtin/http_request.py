import httpx


async def http_request(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: str | None = None,
    timeout: int = 30,
) -> dict:
    """Make an HTTP request and return the response.

    Args:
        url: Target URL.
        method: HTTP method (GET, POST, PUT, DELETE, etc.).
        headers: Optional request headers.
        body: Optional request body (for POST/PUT).
        timeout: Request timeout in seconds (default 30).

    Returns:
        {"status": int, "headers": dict, "body": str}
        On network error: {"status": 0, "error": str}
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method, url, headers=headers, content=body
            )
            return {
                "status": response.status_code,
                "headers": dict(response.headers),
                "body": response.text,
            }
    except Exception as e:
        return {"status": 0, "error": str(e)}
