import httpx
from ..core.config import settings

_TAVILY_URL = "https://api.tavily.com/search"


async def web_search(query: str, num_results: int = 3) -> list[dict]:
    """Search the web via Tavily. Returns list of {title, url, content}."""
    if not settings.tavily_api_key:
        return [{"title": "Error", "url": "", "content": "Tavily API key not configured. Set TAVILY_API_KEY in .env."}]

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            _TAVILY_URL,
            json={
                "api_key": settings.tavily_api_key,
                "query": query,
                "num_results": min(num_results, 5),
                "search_depth": "basic",
                "include_answer": True,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    if data.get("answer"):
        results.append({"title": "Summary", "url": "", "content": data["answer"]})
    for r in data.get("results", []):
        results.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", ""),
        })
    return results
