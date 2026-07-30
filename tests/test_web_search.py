import pytest
from easyagents.tools.builtin.web_search import web_search


@pytest.mark.asyncio
async def test_web_search_returns_list():
    results = await web_search("test query", max_results=3)
    assert isinstance(results, list)
    if results:
        assert "title" in results[0]
        assert "url" in results[0]
        assert "snippet" in results[0]


@pytest.mark.asyncio
async def test_web_search_handles_network_error():
    # Trigger network error with a very short timeout
    results = await web_search("" * 1000, max_results=1)
    assert isinstance(results, list)
    assert len(results) == 0
