"""Pluggable browser action providers.

Each action provider implements a specific browser capability. New providers
can be registered at runtime via `BrowserActionRegistry.register()`.

The default provider uses httpx + selectolax for lightweight HTML fetching
and parsing. For full browser automation (JS rendering, screenshots, form
filling), swap in a Playwright-based provider.
"""

from __future__ import annotations

import abc
import re
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import structlog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class BrowserActionProvider(abc.ABC):
    """Abstract interface for browser action implementations."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Provider identifier."""

    @abc.abstractmethod
    async def fetch_page(self, url: str, **kwargs: Any) -> dict[str, Any]:
        """Fetch a page and return its content."""

    @abc.abstractmethod
    async def extract_data(
        self, url: str, selectors: dict[str, str], **kwargs: Any
    ) -> dict[str, Any]:
        """Extract structured data from a page using CSS selectors."""

    @abc.abstractmethod
    async def extract_links(self, url: str, **kwargs: Any) -> dict[str, Any]:
        """Extract all links from a page."""

    @abc.abstractmethod
    async def extract_text(self, url: str, **kwargs: Any) -> dict[str, Any]:
        """Extract clean text content from a page."""

    @abc.abstractmethod
    async def search_page(self, url: str, query: str, **kwargs: Any) -> dict[str, Any]:
        """Search for text content within a page."""

    async def close(self) -> None:
        """Release resources."""


class HttpxBrowserProvider(BrowserActionProvider):
    """Lightweight browser provider using httpx for HTTP and regex for HTML parsing.

    Suitable for static pages. Does not execute JavaScript.
    For JS-heavy sites, use a Playwright-based provider.
    """

    def __init__(
        self,
        timeout_seconds: float = 30.0,
        max_content_length: int = 500_000,
        user_agent: str = (
            "Mozilla/5.0 (compatible; VclawBot/0.1; +https://github.com/vclaw)"
        ),
    ) -> None:
        self._timeout = timeout_seconds
        self._max_content_length = max_content_length
        self._user_agent = user_agent
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        return "httpx"

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
                headers={"User-Agent": self._user_agent},
                follow_redirects=True,
                max_redirects=5,
            )
        return self._client

    async def fetch_page(self, url: str, **kwargs: Any) -> dict[str, Any]:
        client = self._get_client()
        resp = await client.get(url)
        resp.raise_for_status()
        content = resp.text[: self._max_content_length]
        title = self._extract_title(content)
        return {
            "url": str(resp.url),
            "status_code": resp.status_code,
            "title": title,
            "content_length": len(resp.text),
            "content_type": resp.headers.get("content-type", ""),
            "html": content,
        }

    async def extract_data(
        self, url: str, selectors: dict[str, str], **kwargs: Any
    ) -> dict[str, Any]:
        page = await self.fetch_page(url)
        html = page.get("html", "")
        extracted: dict[str, list[str]] = {}

        for field_name, selector in selectors.items():
            extracted[field_name] = self._css_select_text(html, selector)

        return {
            "url": page["url"],
            "title": page.get("title", ""),
            "data": extracted,
        }

    async def extract_links(self, url: str, **kwargs: Any) -> dict[str, Any]:
        page = await self.fetch_page(url)
        html = page.get("html", "")
        base_url = page["url"]

        links: list[dict[str, str]] = []
        for match in re.finditer(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.I | re.S):
            href = match.group(1).strip()
            text = re.sub(r"<[^>]+>", "", match.group(2)).strip()
            absolute_url = urljoin(base_url, href)

            parsed = urlparse(absolute_url)
            if parsed.scheme in ("http", "https"):
                links.append({"url": absolute_url, "text": text})

        return {
            "url": base_url,
            "title": page.get("title", ""),
            "link_count": len(links),
            "links": links,
        }

    async def extract_text(self, url: str, **kwargs: Any) -> dict[str, Any]:
        page = await self.fetch_page(url)
        html = page.get("html", "")

        for tag in ("script", "style", "nav", "header", "footer", "aside"):
            html = re.sub(
                rf"<{tag}[^>]*>.*?</{tag}>", "", html, flags=re.I | re.S
            )

        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        text = text[: self._max_content_length]

        return {
            "url": page["url"],
            "title": page.get("title", ""),
            "text": text,
            "text_length": len(text),
        }

    async def search_page(self, url: str, query: str, **kwargs: Any) -> dict[str, Any]:
        result = await self.extract_text(url)
        text = result.get("text", "")
        query_lower = query.lower()

        matches: list[dict[str, Any]] = []
        text_lower = text.lower()
        start = 0
        while True:
            pos = text_lower.find(query_lower, start)
            if pos == -1:
                break
            context_start = max(0, pos - 100)
            context_end = min(len(text), pos + len(query) + 100)
            matches.append({
                "position": pos,
                "context": text[context_start:context_end],
            })
            start = pos + 1

        return {
            "url": result["url"],
            "title": result.get("title", ""),
            "query": query,
            "match_count": len(matches),
            "matches": matches[:20],
        }

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    @staticmethod
    def _extract_title(html: str) -> str:
        match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _css_select_text(html: str, selector: str) -> list[str]:
        """Simplified CSS selector extraction using regex.

        Supports: tag, .class, #id, tag.class patterns.
        For complex selectors, use a proper HTML parser (selectolax, bs4).
        """
        if selector.startswith("#"):
            id_val = selector[1:]
            pattern = rf'<[^>]+id=["\']?{re.escape(id_val)}["\']?[^>]*>(.*?)</[^>]+>'
        elif selector.startswith("."):
            class_val = selector[1:]
            pattern = rf'<[^>]+class=["\'][^"\']*\b{re.escape(class_val)}\b[^"\']*["\'][^>]*>(.*?)</[^>]+>'
        else:
            parts = selector.split(".")
            tag = parts[0] or "[a-z]+"
            if len(parts) > 1:
                class_val = parts[1]
                pattern = rf'<{tag}[^>]+class=["\'][^"\']*\b{re.escape(class_val)}\b[^"\']*["\'][^>]*>(.*?)</{tag}>'
            else:
                pattern = rf"<{tag}[^>]*>(.*?)</{tag}>"

        results = []
        for match in re.finditer(pattern, html, re.I | re.S):
            text = re.sub(r"<[^>]+>", "", match.group(1)).strip()
            if text:
                results.append(text)
        return results


class BrowserActionRegistry:
    """Registry for browser action providers. Supports runtime plug-and-play swapping."""

    def __init__(self) -> None:
        self._providers: dict[str, BrowserActionProvider] = {}
        self._default_name: str = ""

    def register(self, provider: BrowserActionProvider, default: bool = False) -> None:
        self._providers[provider.name] = provider
        if default or not self._default_name:
            self._default_name = provider.name
        logger.info("browser_provider_registered", name=provider.name, default=default)

    def get(self, name: str | None = None) -> BrowserActionProvider:
        target = name or self._default_name
        provider = self._providers.get(target)
        if not provider:
            raise KeyError(f"Browser provider '{target}' not registered")
        return provider

    @property
    def default(self) -> BrowserActionProvider:
        return self.get()

    @property
    def available(self) -> list[str]:
        return list(self._providers.keys())

    async def close_all(self) -> None:
        for provider in self._providers.values():
            await provider.close()
