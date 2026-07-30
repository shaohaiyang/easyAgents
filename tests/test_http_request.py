import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from easyagents.tools.builtin.http_request import http_request


@pytest.mark.asyncio
async def test_http_request_returns_response():
    """Test http_request returns status, headers, body."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.text = '{"key": "value"}'

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.request = AsyncMock(return_value=mock_response)

    with patch("easyagents.tools.builtin.http_request.httpx.AsyncClient", return_value=mock_client):
        result = await http_request("https://example.com/api")

    assert result["status"] == 200
    assert result["body"] == '{"key": "value"}'
    assert "content-type" in result["headers"]


@pytest.mark.asyncio
async def test_http_request_network_error():
    """Test http_request returns error dict on network failure."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("easyagents.tools.builtin.http_request.httpx.AsyncClient", return_value=mock_client):
        result = await http_request("https://example.com")

    assert result["status"] == 0
    assert "error" in result


@pytest.mark.asyncio
async def test_http_request_post_with_body():
    """Test http_request sends POST with body."""
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.headers = {}
    mock_response.text = "Created"

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.request = AsyncMock(return_value=mock_response)

    with patch("easyagents.tools.builtin.http_request.httpx.AsyncClient", return_value=mock_client):
        result = await http_request(
            "https://example.com/api",
            method="POST",
            body='{"name": "test"}',
        )

    assert result["status"] == 201
    mock_client.request.assert_called_once_with(
        "POST", "https://example.com/api",
        headers=None, content='{"name": "test"}',
    )
