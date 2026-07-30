import asyncio
import logging

logger = logging.getLogger(__name__)


async def web_search(
    query: str, max_results: int = 5
) -> list[dict[str, str]]:
    """Search the web using DuckDuckGo and return results.

    Args:
        query: Search query string.
        max_results: Maximum number of results to return (default 5).

    Returns:
        A list of dicts with keys: title, url, snippet.
        Returns an empty list on network errors.
    """
    try:
        from duckduckgo_search import DDGS

        def _search() -> list[dict[str, str]]:
            results: list[dict[str, str]] = []
            with DDGS() as ddgs:
                for i, r in enumerate(ddgs.text(query, max_results=max_results)):
                    if i >= max_results:
                        break
                    results.append(
                        {
                            "title": r.get("title", ""),
                            "url": r.get("href", ""),
                            "snippet": r.get("body", ""),
                        }
                    )
            return results

        return await asyncio.to_thread(_search)
    except Exception as e:
        logger.warning("Web search failed for query '%s': %s", query, e)
        return []
