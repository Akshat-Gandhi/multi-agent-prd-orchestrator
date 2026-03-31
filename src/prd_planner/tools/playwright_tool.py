from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx


def _merge_query_params(url: str, params: dict[str, str]) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update({k: v for k, v in params.items() if v})
    return urlunparse(parsed._replace(query=urlencode(query)))


def _extract_text_content(content: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for item in content:
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    return "\n".join(parts).strip()


class PlaywrightMCPClient(Protocol):
    def open_page(self, url: str) -> str:
        ...

    def extract_facts(self, page_id: str) -> list[str]:
        ...

    def close_page(self, page_id: str) -> None:
        ...


@dataclass
class DummyPlaywrightMCPClient:
    closed_pages: list[str] = field(default_factory=list)

    def open_page(self, url: str) -> str:
        return f"page:{url}"

    def extract_facts(self, page_id: str) -> list[str]:
        return [
            f"Extracted evidence from {page_id}",
            "Pricing page appears to offer tiered plans",
        ]

    def close_page(self, page_id: str) -> None:
        self.closed_pages.append(page_id)


@dataclass
class RemotePlaywrightMCPClient:
    mcp_url: str
    api_key: str = ""
    timeout_s: float = 60.0
    open_tool: str = "browser_open_page"
    extract_tool: str = "browser_extract_facts"
    close_tool: str = "browser_close_page"

    def _endpoint(self) -> str:
        return _merge_query_params(self.mcp_url, {"apiKey": self.api_key})

    def _call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        body = {
            "jsonrpc": "2.0",
            "id": f"pw-{name}",
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        response = httpx.post(self._endpoint(), json=body, timeout=self.timeout_s)
        response.raise_for_status()
        payload = response.json()
        if "error" in payload:
            raise RuntimeError(f"playwright mcp error: {payload['error']}")
        return payload.get("result", {})

    def open_page(self, url: str) -> str:
        result = self._call_tool(self.open_tool, {"url": url})
        content = result.get("content", [])
        text = _extract_text_content(content) if isinstance(content, list) else ""
        if text:
            return f"remote:{text.splitlines()[0][:120]}"
        return f"remote:{url}"

    def extract_facts(self, page_id: str) -> list[str]:
        result = self._call_tool(self.extract_tool, {"page_id": page_id})
        content = result.get("content", [])
        text = _extract_text_content(content) if isinstance(content, list) else ""
        if not text:
            return []
        return [line.strip(" -") for line in text.splitlines() if line.strip()][:8]

    def close_page(self, page_id: str) -> None:
        self._call_tool(self.close_tool, {"page_id": page_id})


@dataclass
class SafePlaywrightMCPClient:
    primary: PlaywrightMCPClient
    fallback: PlaywrightMCPClient
    route: dict[str, str] = field(default_factory=dict)

    def open_page(self, url: str) -> str:
        try:
            page_id = self.primary.open_page(url)
            self.route[page_id] = "primary"
            return page_id
        except Exception:
            page_id = self.fallback.open_page(url)
            self.route[page_id] = "fallback"
            return page_id

    def extract_facts(self, page_id: str) -> list[str]:
        backend = self.route.get(page_id, "fallback")
        if backend == "primary":
            try:
                return self.primary.extract_facts(page_id)
            except Exception:
                return self.fallback.extract_facts(page_id)
        return self.fallback.extract_facts(page_id)

    def close_page(self, page_id: str) -> None:
        backend = self.route.get(page_id, "fallback")
        if backend == "primary":
            try:
                self.primary.close_page(page_id)
                return
            except Exception:
                pass
        self.fallback.close_page(page_id)


@dataclass
class BrowserSessionResult:
    opened: bool
    closed: bool
    facts: list[str]


class PlaywrightLifecycleTool:
    def __init__(self, client: PlaywrightMCPClient) -> None:
        self.client = client

    def capture(self, url: str) -> BrowserSessionResult:
        page_id = ""
        opened = False
        facts: list[str] = []
        try:
            page_id = self.client.open_page(url)
            opened = True
            facts = self.client.extract_facts(page_id)
            return BrowserSessionResult(opened=opened, closed=False, facts=facts)
        finally:
            if page_id:
                self.client.close_page(page_id)


def build_playwright_tool_from_env() -> PlaywrightLifecycleTool:
    fallback = DummyPlaywrightMCPClient()
    mcp_url = os.getenv("PLAYWRIGHT_MCP_URL", "").strip()
    if not mcp_url:
        return PlaywrightLifecycleTool(client=fallback)

    client = SafePlaywrightMCPClient(
        primary=RemotePlaywrightMCPClient(
            mcp_url=mcp_url,
            api_key=os.getenv("PLAYWRIGHT_MCP_API_KEY", "").strip(),
            timeout_s=float(os.getenv("PLAYWRIGHT_MCP_TIMEOUT_S", "60")),
            open_tool=os.getenv("PLAYWRIGHT_MCP_OPEN_TOOL", "browser_open_page"),
            extract_tool=os.getenv("PLAYWRIGHT_MCP_EXTRACT_TOOL", "browser_extract_facts"),
            close_tool=os.getenv("PLAYWRIGHT_MCP_CLOSE_TOOL", "browser_close_page"),
        ),
        fallback=fallback,
    )
    return PlaywrightLifecycleTool(client=client)
