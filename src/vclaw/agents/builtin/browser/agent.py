"""BrowserAgent — plug-and-play web browsing, scraping, and automation.

Backend selection (automatic, no configuration required):
  1. Playwright (async)  — full JS rendering, screenshots, form filling, clicks
  2. httpx               — lightweight fallback for static HTML / JSON endpoints

Install Playwright for full capability:
    pip install playwright
    playwright install chromium

Without Playwright, the agent still works for static pages and APIs via httpx.
"""

from __future__ import annotations

import base64
import json
import re
from typing import Any, ClassVar
from urllib.parse import urljoin, urlparse

import httpx
import structlog

from vclaw.agents.base import AgentBase
from vclaw.domain.models import (
    AgentCapability,
    AgentManifest,
    AgentRequest,
    AgentResponse,
    LLMRequest,
    RetryPolicy,
    ToolDefinition,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Playwright availability flag — checked once at import time
try:
    from playwright.async_api import (
        Browser,
        BrowserContext,
        Page,
        async_playwright,
    )

    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False
    logger.info(
        "playwright_not_installed",
        fallback="httpx",
        hint="pip install playwright && playwright install chromium",
    )


_DEFAULT_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
_DEFAULT_TIMEOUT = 30_000  # ms for Playwright; seconds/1000 for httpx


def _strip_html_tags(html: str) -> str:
    """Best-effort plain text extraction without heavy dependencies."""
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:8000]  # keep context window manageable


def _extract_links(html: str, base_url: str) -> list[dict[str, str]]:
    """Extract href links from raw HTML."""
    pattern = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
    links = []
    for m in pattern.finditer(html):
        href, text = m.group(1), re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if href.startswith(("http", "//")):
            full = href
        elif href.startswith("/"):
            parsed = urlparse(base_url)
            full = f"{parsed.scheme}://{parsed.netloc}{href}"
        else:
            full = urljoin(base_url, href)
        if text and len(links) < 30:
            links.append({"text": text, "url": full})
    return links


class BrowserAgent(AgentBase):
    """Web browsing, scraping, and browser automation agent.

    Capabilities
    ------------
    - **fetch_page**: Load any URL, return text content, links, and optional screenshot.
    - **extract_data**: Load a URL and run an LLM-powered extraction prompt to pull
      structured data (prices, tables, article text, etc.).
    - **click_element**: Click a CSS-selector element on a page (Playwright only).
    - **fill_form**: Fill and submit a web form (Playwright only).
    - **search_web**: Perform a search via a search engine URL and return results.
    - **take_screenshot**: Capture a full-page screenshot (Playwright only).

    All tools degrade gracefully to httpx when Playwright is not installed.
    Tools that *require* Playwright return a clear error when it is absent.

    Configuration (environment variables, all optional)
    ---------------------------------------------------
    BROWSER_HEADLESS       true/false (default: true)
    BROWSER_TIMEOUT_MS     per-action timeout ms (default: 30000)
    BROWSER_USER_AGENT     custom UA string
    BROWSER_PROXY          proxy URL (e.g. http://user:pass@host:port)
    """

    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="browser",
        version="0.1.0",
        description=(
            "Web browser agent: fetches pages, extracts structured data, "
            "performs form interactions, and captures screenshots. "
            "Uses Playwright for full JS rendering; falls back to httpx for static pages."
        ),
        capabilities=[
            AgentCapability(
                name="web_browsing",
                description="Load and read any public web page, follow links, extract text and data",
            ),
            AgentCapability(
                name="web_scraping",
                description="Extract structured data from web pages using CSS selectors or LLM extraction",
            ),
            AgentCapability(
                name="web_automation",
                description="Fill forms, click buttons, and automate browser interactions",
            ),
            AgentCapability(
                name="screenshot",
                description="Capture full-page screenshots of any URL",
            ),
        ],
        tools=[
            ToolDefinition(
                name="fetch_page",
                description="Fetch a web page and return its text content and links",
                parameters={
                    "url": {"type": "string", "description": "Full URL to fetch (must include http/https)"},
                    "wait_for_selector": {
                        "type": "string",
                        "description": "CSS selector to wait for before extracting content (Playwright only)",
                    },
                    "include_links": {
                        "type": "boolean",
                        "description": "Whether to extract hyperlinks from the page (default: true)",
                    },
                },
                required_params=["url"],
            ),
            ToolDefinition(
                name="extract_data",
                description=(
                    "Fetch a URL and extract structured data by describing what you want "
                    "(e.g. 'product prices', 'article headlines', 'contact information')"
                ),
                parameters={
                    "url": {"type": "string", "description": "URL to scrape"},
                    "extraction_prompt": {
                        "type": "string",
                        "description": "Natural language description of what data to extract",
                    },
                },
                required_params=["url", "extraction_prompt"],
            ),
            ToolDefinition(
                name="click_element",
                description="Click a CSS-selector element on a page (requires Playwright)",
                parameters={
                    "url": {"type": "string", "description": "URL to open"},
                    "selector": {"type": "string", "description": "CSS selector of the element to click"},
                    "wait_for_navigation": {
                        "type": "boolean",
                        "description": "Wait for page navigation after click (default: true)",
                    },
                },
                required_params=["url", "selector"],
            ),
            ToolDefinition(
                name="fill_form",
                description="Fill and submit a web form (requires Playwright)",
                parameters={
                    "url": {"type": "string", "description": "URL of the page with the form"},
                    "fields": {
                        "type": "object",
                        "description": 'Map of CSS selector → value, e.g. {"#username": "alice", "#password": "secret"}',
                    },
                    "submit_selector": {
                        "type": "string",
                        "description": "CSS selector of the submit button",
                    },
                },
                required_params=["url", "fields"],
            ),
            ToolDefinition(
                name="take_screenshot",
                description="Capture a full-page screenshot (requires Playwright). Returns base64 PNG.",
                parameters={
                    "url": {"type": "string", "description": "URL to screenshot"},
                    "full_page": {
                        "type": "boolean",
                        "description": "Capture full scrollable page (default: true)",
                    },
                },
                required_params=["url"],
            ),
            ToolDefinition(
                name="search_web",
                description="Perform a web search and return the top results",
                parameters={
                    "query": {"type": "string", "description": "Search query"},
                    "engine": {
                        "type": "string",
                        "enum": ["duckduckgo", "bing", "google"],
                        "description": "Search engine to use (default: duckduckgo)",
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 5)",
                    },
                },
                required_params=["query"],
            ),
        ],
        max_concurrent=3,
        timeout_seconds=60.0,
        retry_policy=RetryPolicy(max_retries=1, base_delay_seconds=2.0),
        tags=["browser", "scraping", "automation", "web"],
    )

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._http_client: httpx.AsyncClient | None = None

    async def setup(self) -> None:
        await super().setup()
        self._http_client = httpx.AsyncClient(
            headers={"User-Agent": _DEFAULT_UA},
            timeout=_DEFAULT_TIMEOUT / 1000,
            follow_redirects=True,
        )

    async def teardown(self) -> None:
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def execute(self, request: AgentRequest) -> AgentResponse:
        text = request.input_data.get("text", "")
        if not text:
            return AgentResponse(
                workflow_id=request.workflow_id,
                subtask_id=request.subtask_id,
                agent_name=self.name,
                success=False,
                error="No input text provided",
            )

        try:
            llm_resp = await self.call_llm(
                LLMRequest(
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a web browsing assistant. Use the available tools to "
                                "fulfill the user's request. Always use a tool call.\n"
                                f"Playwright available: {_PLAYWRIGHT_AVAILABLE}"
                            ),
                        },
                        {"role": "user", "content": text},
                    ],
                    tools=self.get_tool_schemas(),
                    tool_choice="auto",
                    temperature=0.0,
                )
            )
        except Exception as exc:
            return await self._fallback_execution(request, str(exc))

        if llm_resp.tool_calls:
            return await self._handle_tool_calls(request, llm_resp.tool_calls)

        return AgentResponse(
            workflow_id=request.workflow_id,
            subtask_id=request.subtask_id,
            agent_name=self.name,
            success=True,
            data={"response_text": llm_resp.content or "Browser task completed."},
        )

    # ------------------------------------------------------------------
    # Tool dispatch
    # ------------------------------------------------------------------

    async def _handle_tool_calls(
        self, request: AgentRequest, tool_calls: list[dict[str, Any]]
    ) -> AgentResponse:
        results: list[dict[str, Any]] = []
        response_parts: list[str] = []

        for tc in tool_calls:
            func = tc.get("function", {})
            name = func.get("name", "")
            try:
                args: dict[str, Any] = json.loads(func.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}

            result = await self._execute_tool(name, args)
            results.append({"tool": name, "result": result})

            if result.get("success"):
                response_parts.append(self._format_tool_result(name, result["data"]))
            else:
                response_parts.append(f"❌ {result.get('error', 'Unknown error')}")

        return AgentResponse(
            workflow_id=request.workflow_id,
            subtask_id=request.subtask_id,
            agent_name=self.name,
            success=True,
            data={
                "response_text": "\n\n".join(response_parts),
                "tool_results": results,
            },
        )

    def _format_tool_result(self, tool_name: str, data: Any) -> str:
        if not isinstance(data, dict):
            return str(data)

        if tool_name == "fetch_page":
            title = data.get("title", "")
            url = data.get("url", "")
            content = data.get("content", "")[:500]
            links = data.get("links", [])[:5]
            parts = [f"🌐 **{title or url}**", f"`{url}`", "", content]
            if links:
                parts += ["", "🔗 Links:"] + [f"  • [{lk['text']}]({lk['url']})" for lk in links]
            return "\n".join(parts)

        if tool_name == "extract_data":
            extracted = data.get("extracted", "")
            url = data.get("url", "")
            return f"📊 Extracted from `{url}`:\n{extracted}"

        if tool_name == "take_screenshot":
            url = data.get("url", "")
            return f"📸 Screenshot captured: `{url}` ({data.get('size_kb', '?')} KB)"

        if tool_name == "search_web":
            results = data.get("results", [])
            lines = [f"🔍 Search results for: **{data.get('query', '')}**"]
            for r in results:
                lines.append(f"  • [{r.get('title', '?')}]({r.get('url', '')}) — {r.get('snippet', '')[:80]}")
            return "\n".join(lines)

        if tool_name in ("click_element", "fill_form"):
            return f"✅ {tool_name.replace('_', ' ').title()} completed on `{data.get('url', '')}`"

        return str(data)

    async def _execute_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        try:
            if name == "fetch_page":
                return await self._fetch_page(**args)
            elif name == "extract_data":
                return await self._extract_data(**args)
            elif name == "click_element":
                return await self._click_element(**args)
            elif name == "fill_form":
                return await self._fill_form(**args)
            elif name == "take_screenshot":
                return await self._take_screenshot(**args)
            elif name == "search_web":
                return await self._search_web(**args)
            else:
                return {"success": False, "error": f"Unknown tool: {name}"}
        except Exception as exc:
            logger.exception("browser_tool_error", tool=name, url=args.get("url", ""))
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    async def _fetch_page(
        self,
        url: str,
        wait_for_selector: str = "",
        include_links: bool = True,
        **_: Any,
    ) -> dict[str, Any]:
        if _PLAYWRIGHT_AVAILABLE and wait_for_selector:
            return await self._playwright_fetch(url, wait_for_selector, include_links)
        return await self._httpx_fetch(url, include_links)

    async def _httpx_fetch(self, url: str, include_links: bool = True) -> dict[str, Any]:
        client = self._http_client or httpx.AsyncClient(
            headers={"User-Agent": _DEFAULT_UA},
            timeout=_DEFAULT_TIMEOUT / 1000,
            follow_redirects=True,
        )
        resp = await client.get(url)
        resp.raise_for_status()
        html = resp.text
        content = _strip_html_tags(html)

        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else ""

        result: dict[str, Any] = {
            "url": str(resp.url),
            "status_code": resp.status_code,
            "title": title,
            "content": content,
            "backend": "httpx",
        }
        if include_links:
            result["links"] = _extract_links(html, str(resp.url))
        return {"success": True, "data": result}

    async def _playwright_fetch(
        self, url: str, wait_for_selector: str, include_links: bool
    ) -> dict[str, Any]:
        async with async_playwright() as pw:
            browser: Browser = await pw.chromium.launch(headless=True)
            ctx: BrowserContext = await browser.new_context(user_agent=_DEFAULT_UA)
            page: Page = await ctx.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=_DEFAULT_TIMEOUT)
            if wait_for_selector:
                await page.wait_for_selector(wait_for_selector, timeout=_DEFAULT_TIMEOUT)
            html = await page.content()
            title = await page.title()
            await browser.close()

        content = _strip_html_tags(html)
        result: dict[str, Any] = {
            "url": url,
            "title": title,
            "content": content,
            "backend": "playwright",
        }
        if include_links:
            result["links"] = _extract_links(html, url)
        return {"success": True, "data": result}

    async def _extract_data(self, url: str, extraction_prompt: str, **_: Any) -> dict[str, Any]:
        fetch_result = await self._fetch_page(url)
        if not fetch_result["success"]:
            return fetch_result

        page_content = fetch_result["data"]["content"]
        title = fetch_result["data"].get("title", "")

        if not self._llm_router:
            return {
                "success": True,
                "data": {
                    "url": url,
                    "extracted": f"[LLM not available] Raw content:\n{page_content[:2000]}",
                },
            }

        llm_resp = await self.call_llm(
            LLMRequest(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a data extraction assistant. "
                            "Extract the requested information from the web page content. "
                            "Be concise and structured. If information is not found, say so."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Page title: {title}\nURL: {url}\n\n"
                            f"Page content:\n{page_content}\n\n"
                            f"Extract: {extraction_prompt}"
                        ),
                    },
                ],
                temperature=0.0,
                max_tokens=2048,
            )
        )
        return {
            "success": True,
            "data": {
                "url": url,
                "extraction_prompt": extraction_prompt,
                "extracted": llm_resp.content,
            },
        }

    async def _click_element(
        self,
        url: str,
        selector: str,
        wait_for_navigation: bool = True,
        **_: Any,
    ) -> dict[str, Any]:
        if not _PLAYWRIGHT_AVAILABLE:
            return {"success": False, "error": "click_element requires Playwright. Install: pip install playwright && playwright install chromium"}

        async with async_playwright() as pw:
            browser: Browser = await pw.chromium.launch(headless=True)
            ctx: BrowserContext = await browser.new_context(user_agent=_DEFAULT_UA)
            page: Page = await ctx.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=_DEFAULT_TIMEOUT)
            await page.click(selector)
            if wait_for_navigation:
                await page.wait_for_load_state("networkidle", timeout=_DEFAULT_TIMEOUT)
            final_url = page.url
            title = await page.title()
            await browser.close()

        return {
            "success": True,
            "data": {"url": final_url, "title": title, "action": f"clicked {selector}"},
        }

    async def _fill_form(
        self,
        url: str,
        fields: dict[str, str],
        submit_selector: str = "",
        **_: Any,
    ) -> dict[str, Any]:
        if not _PLAYWRIGHT_AVAILABLE:
            return {"success": False, "error": "fill_form requires Playwright. Install: pip install playwright && playwright install chromium"}

        async with async_playwright() as pw:
            browser: Browser = await pw.chromium.launch(headless=True)
            ctx: BrowserContext = await browser.new_context(user_agent=_DEFAULT_UA)
            page: Page = await ctx.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=_DEFAULT_TIMEOUT)

            for selector, value in fields.items():
                await page.fill(selector, str(value))

            if submit_selector:
                await page.click(submit_selector)
                await page.wait_for_load_state("networkidle", timeout=_DEFAULT_TIMEOUT)

            final_url = page.url
            title = await page.title()
            await browser.close()

        return {
            "success": True,
            "data": {
                "url": final_url,
                "title": title,
                "fields_filled": list(fields.keys()),
                "submitted": bool(submit_selector),
            },
        }

    async def _take_screenshot(self, url: str, full_page: bool = True, **_: Any) -> dict[str, Any]:
        if not _PLAYWRIGHT_AVAILABLE:
            return {"success": False, "error": "take_screenshot requires Playwright. Install: pip install playwright && playwright install chromium"}

        async with async_playwright() as pw:
            browser: Browser = await pw.chromium.launch(headless=True)
            ctx: BrowserContext = await browser.new_context(user_agent=_DEFAULT_UA)
            page: Page = await ctx.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=_DEFAULT_TIMEOUT)
            screenshot_bytes: bytes = await page.screenshot(full_page=full_page)
            title = await page.title()
            await browser.close()

        b64 = base64.b64encode(screenshot_bytes).decode("ascii")
        return {
            "success": True,
            "data": {
                "url": url,
                "title": title,
                "screenshot_base64": b64,
                "size_kb": round(len(screenshot_bytes) / 1024, 1),
                "full_page": full_page,
            },
        }

    async def _search_web(
        self,
        query: str,
        engine: str = "duckduckgo",
        num_results: int = 5,
        **_: Any,
    ) -> dict[str, Any]:
        search_urls = {
            "duckduckgo": f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}",
            "bing": f"https://www.bing.com/search?q={query.replace(' ', '+')}",
            "google": f"https://www.google.com/search?q={query.replace(' ', '+')}",
        }
        search_url = search_urls.get(engine, search_urls["duckduckgo"])
        fetch_result = await self._fetch_page(search_url, include_links=True)

        if not fetch_result["success"]:
            return fetch_result

        links = fetch_result["data"].get("links", [])
        content = fetch_result["data"].get("content", "")

        results: list[dict[str, str]] = []
        seen_urls: set[str] = set()
        for lk in links:
            lk_url: str = lk.get("url", "")
            lk_text: str = lk.get("text", "")
            if (
                lk_url
                and lk_url not in seen_urls
                and not lk_url.startswith("https://html.duckduckgo.com")
                and lk_text
                and len(lk_text) > 5
            ):
                results.append({"title": lk_text, "url": lk_url, "snippet": ""})
                seen_urls.add(lk_url)
            if len(results) >= num_results:
                break

        return {
            "success": True,
            "data": {
                "query": query,
                "engine": engine,
                "results": results,
                "raw_content_preview": content[:300],
            },
        }

    # ------------------------------------------------------------------
    # LLM-unavailable fallback
    # ------------------------------------------------------------------

    async def _fallback_execution(self, request: AgentRequest, error: str) -> AgentResponse:
        """Direct URL fetch when LLM is unavailable."""
        text = request.input_data.get("text", "")
        url_match = re.search(r"https?://[^\s]+", text)

        if url_match:
            url = url_match.group(0)
            fetch_result = await self._fetch_page(url)
            if fetch_result["success"]:
                data = fetch_result["data"]
                return AgentResponse(
                    workflow_id=request.workflow_id,
                    subtask_id=request.subtask_id,
                    agent_name=self.name,
                    success=True,
                    data={
                        "response_text": (
                            f"🌐 **{data.get('title', url)}**\n"
                            f"`{url}`\n\n"
                            f"{data.get('content', '')[:500]}"
                        ),
                        **fetch_result["data"],
                    },
                    metadata={"fallback": True, "llm_error": error},
                )

        return AgentResponse(
            workflow_id=request.workflow_id,
            subtask_id=request.subtask_id,
            agent_name=self.name,
            success=False,
            error=(
                f"LLM unavailable and no URL found in input. "
                f"Provide a URL or ensure LLM is configured. LLM error: {error}"
            ),
        )
