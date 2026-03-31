from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from prd_planner.contracts.schemas import Citation


def _merge_query_params(url: str, params: dict[str, str]) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update({k: v for k, v in params.items() if v})
    return urlunparse(parsed._replace(query=urlencode(query)))


def _collect_citations_from_obj(obj: Any, out: list[Citation], limit: int) -> None:
    if len(out) >= limit:
        return
    if isinstance(obj, dict):
        title = obj.get("title")
        url = obj.get("url")
        snippet = obj.get("text") or obj.get("snippet")
        if isinstance(title, str) and isinstance(url, str):
            out.append(Citation(title=title, url=url, snippet=snippet if isinstance(snippet, str) else None))
            if len(out) >= limit:
                return
        for value in obj.values():
            _collect_citations_from_obj(value, out, limit)
            if len(out) >= limit:
                return
    elif isinstance(obj, list):
        for value in obj:
            _collect_citations_from_obj(value, out, limit)
            if len(out) >= limit:
                return


def _extract_tool_text(content: list[dict[str, Any]]) -> str | None:
    for part in content:
        text = part.get("text")
        if isinstance(text, str) and text.strip():
            return text
    return None


class ExaMCPClient(Protocol):
    def search(self, query: str, limit: int = 5) -> list[Citation]:
        ...


class ExaAPIClient(Protocol):
    def search(self, query: str, limit: int = 5) -> list[Citation]:
        ...


@dataclass
class DummyExaMCPClient:
    should_fail: bool = False

    def search(self, query: str, limit: int = 5) -> list[Citation]:
        if self.should_fail:
            raise RuntimeError("MCP unavailable")
        return []


@dataclass
class DummyExaAPIClient:
    def search(self, query: str, limit: int = 5) -> list[Citation]:
        return []


@dataclass
class RemoteExaMCPClient:
    """
    Remote MCP client for Exa using streamable HTTP MCP endpoint.
    """

    mcp_url: str = "https://mcp.exa.ai/mcp"
    exa_api_key: str = ""
    timeout_s: float = 45.0

    def _endpoint(self) -> str:
        return _merge_query_params(
            self.mcp_url,
            {
                "exaApiKey": self.exa_api_key,
                "tools": "web_search_exa,crawling_exa,get_code_context_exa",
            },
        )

    def search(self, query: str, limit: int = 5) -> list[Citation]:
        endpoint = self._endpoint()
        body = {
            "jsonrpc": "2.0",
            "id": "exa-search-1",
            "method": "tools/call",
            "params": {
                "name": "web_search_exa",
                "arguments": {"query": query, "numResults": limit},
            },
        }
        response = httpx.post(endpoint, json=body, timeout=self.timeout_s)
        response.raise_for_status()
        payload = response.json()

        if "error" in payload:
            raise RuntimeError(f"exa mcp error: {payload['error']}")

        result = payload.get("result", {})
        content = result.get("content", [])
        text_blob = _extract_tool_text(content) if isinstance(content, list) else None

        parsed_obj: Any = result
        if text_blob:
            try:
                import json as _json

                parsed_obj = _json.loads(text_blob)
            except Exception:
                parsed_obj = {"content_text": text_blob}

        citations: list[Citation] = []
        _collect_citations_from_obj(parsed_obj, citations, limit)
        if citations:
            return citations
        raise RuntimeError("exa mcp returned no citations")


@dataclass
class ExaAPIHttpClient:
    """
    Direct Exa API fallback client.
    """

    api_key: str
    base_url: str = "https://api.exa.ai"
    timeout_s: float = 45.0

    def search(self, query: str, limit: int = 5) -> list[Citation]:
        url = f"{self.base_url.rstrip('/')}/search"
        headers = {"x-api-key": self.api_key, "Content-Type": "application/json"}
        body = {
            "query": query,
            "numResults": limit,
            "contents": {"text": True},
        }
        response = httpx.post(url, json=body, headers=headers, timeout=self.timeout_s)
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results", [])

        citations: list[Citation] = []
        for item in results:
            if len(citations) >= limit:
                break
            title = item.get("title")
            url_value = item.get("url")
            text = item.get("text")
            if isinstance(title, str) and isinstance(url_value, str):
                citations.append(Citation(title=title, url=url_value, snippet=text if isinstance(text, str) else None))

        if citations:
            return citations
        raise RuntimeError("exa api returned no citations")


@dataclass
class ExaSearchStrategy:
    mcp: ExaMCPClient
    api: ExaAPIClient
    default_limit: int = 5

    def search(self, query: str, limit: int = 5) -> tuple[list[Citation], str]:
        effective_limit = max(1, min(limit, self.default_limit))
        try:
            return self.mcp.search(query, limit=effective_limit), "mcp"
        except Exception:
            return self.api.search(query, limit=effective_limit), "api_fallback"


def build_exa_strategy_from_env() -> ExaSearchStrategy:
    exa_key = os.getenv("EXA_API_KEY", "").strip()
    exa_mcp_url = os.getenv("EXA_MCP_URL", "https://mcp.exa.ai/mcp").strip()
    exa_api_base_url = os.getenv("EXA_API_BASE_URL", "https://api.exa.ai").strip()
    exa_timeout_s = float(os.getenv("EXA_TIMEOUT_S", "45"))
    exa_num_results = int(os.getenv("EXA_NUM_RESULTS", "5"))

    if exa_key:
        return ExaSearchStrategy(
            mcp=RemoteExaMCPClient(mcp_url=exa_mcp_url, exa_api_key=exa_key, timeout_s=exa_timeout_s),
            api=ExaAPIHttpClient(api_key=exa_key, base_url=exa_api_base_url, timeout_s=exa_timeout_s),
            default_limit=exa_num_results,
        )
    return ExaSearchStrategy(mcp=DummyExaMCPClient(), api=DummyExaAPIClient(), default_limit=exa_num_results)
