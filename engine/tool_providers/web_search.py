"""
Web Search tool provider — Brave Search API integration.

Lets Claude search the web for current information during any session.
Packs opt in via manifest tool declaration.
"""
import logging
import os

import httpx

from tool_providers.base import ToolProvider

logger = logging.getLogger("tmos13.tools.web_search")

_BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


class WebSearchProvider(ToolProvider):
    """Provider for web search via Brave Search API."""

    @property
    def name(self) -> str:
        return "web_search"

    def supported_operations(self) -> list[str]:
        return ["search"]

    async def execute(
        self,
        operation: str,
        parameters: dict,
        config: dict,
    ) -> dict:
        if operation == "search":
            return await self._search(parameters, config)
        return {"success": False, "message": f"Unsupported operation: {operation}"}

    async def _search(self, parameters: dict, config: dict) -> dict:
        from config import WEB_SEARCH_ENABLED, WEB_SEARCH_MAX_RESULTS

        if not WEB_SEARCH_ENABLED:
            return {"success": False, "message": "Web search is disabled."}

        api_key = os.environ.get("BRAVE_SEARCH_API_KEY", "")
        if not api_key:
            return {"success": False, "message": "Web search is not configured (missing API key)."}

        query = parameters.get("query", "").strip()
        if not query:
            return {"success": False, "message": "Missing required parameter: query"}

        num_results = parameters.get("num_results", WEB_SEARCH_MAX_RESULTS)
        num_results = max(1, min(10, int(num_results)))

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    _BRAVE_ENDPOINT,
                    params={"q": query, "count": num_results},
                    headers={
                        "Accept": "application/json",
                        "Accept-Encoding": "gzip",
                        "X-Subscription-Token": api_key,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            web_results = data.get("web", {}).get("results", [])
            results = []
            for item in web_results[:num_results]:
                results.append({
                    "title": item.get("title", ""),
                    "snippet": (item.get("description", "") or "")[:500],
                    "url": item.get("url", ""),
                })

            if not results:
                return {
                    "success": True,
                    "message": f"No results found for: {query}",
                    "results": [],
                    "query": query,
                }

            # Format for conversational display
            lines = [f"Web search results for: {query}\n"]
            for i, r in enumerate(results, 1):
                lines.append(f"{i}. {r['title']}")
                lines.append(f"   {r['snippet']}")
                lines.append(f"   {r['url']}")
                lines.append("")

            return {
                "success": True,
                "message": "\n".join(lines),
                "results": results,
                "query": query,
            }

        except httpx.HTTPStatusError as e:
            logger.warning("Brave Search API error: %s %s", e.response.status_code, e.response.text[:200])
            return {"success": False, "message": f"Search API error (HTTP {e.response.status_code})."}
        except httpx.TimeoutException:
            return {"success": False, "message": "Search request timed out. Please try again."}
        except Exception as e:
            logger.error("Web search failed: %s", e)
            return {"success": False, "message": f"Search failed: {e}"}
