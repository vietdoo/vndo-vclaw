"""Browser automation agent with LLM-powered action selection.

Provides web scraping, data extraction, link crawling, text extraction,
and page searching capabilities through a pluggable action provider system.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

import structlog

from vclaw.agents.base import AgentBase
from vclaw.agents.builtin.browser.actions import (
    BrowserActionRegistry,
    HttpxBrowserProvider,
)
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


class BrowserAgent(AgentBase):
    """Agent for browser-based data retrieval and web automation.

    Features:
    - Fetch and render web pages
    - Extract structured data via CSS selectors
    - Extract and follow links
    - Full-text search within pages
    - Clean text extraction (strips scripts/styles/nav)
    - Pluggable provider architecture (httpx default, Playwright optional)

    The agent uses LLM tool-calling to interpret natural language requests
    into specific browser actions, with keyword-based fallback when LLM
    is unavailable.
    """

    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="browser",
        version="0.1.0",
        description=(
            "Browser automation agent: fetch web pages, extract data, "
            "scrape content, follow links, and search within pages. "
            "Supports both static HTTP fetching and pluggable browser engines."
        ),
        capabilities=[
            AgentCapability(
                name="web_scraping",
                description="Fetch and extract data from web pages",
            ),
            AgentCapability(
                name="web_browsing",
                description="Browse web pages and retrieve content",
            ),
            AgentCapability(
                name="data_extraction",
                description="Extract structured data from HTML using selectors",
            ),
            AgentCapability(
                name="link_extraction",
                description="Extract and analyze links from web pages",
            ),
        ],
        tools=[
            ToolDefinition(
                name="fetch_page",
                description=(
                    "Fetch a web page and return its HTML content, title, "
                    "and metadata. Use for getting raw page content."
                ),
                parameters={
                    "url": {
                        "type": "string",
                        "description": "Full URL to fetch (must start with http:// or https://)",
                    },
                },
                required_params=["url"],
            ),
            ToolDefinition(
                name="extract_text",
                description=(
                    "Extract clean readable text from a web page, "
                    "stripping scripts, styles, and navigation elements."
                ),
                parameters={
                    "url": {
                        "type": "string",
                        "description": "URL to extract text from",
                    },
                },
                required_params=["url"],
            ),
            ToolDefinition(
                name="extract_links",
                description="Extract all hyperlinks from a web page with their anchor text.",
                parameters={
                    "url": {
                        "type": "string",
                        "description": "URL to extract links from",
                    },
                },
                required_params=["url"],
            ),
            ToolDefinition(
                name="extract_data",
                description=(
                    "Extract structured data from a page using CSS selectors. "
                    "Provide a mapping of field names to CSS selectors."
                ),
                parameters={
                    "url": {
                        "type": "string",
                        "description": "URL to extract data from",
                    },
                    "selectors": {
                        "type": "object",
                        "description": (
                            "Mapping of field names to CSS selectors "
                            '(e.g. {"title": "h1", "prices": ".price"})'
                        ),
                    },
                },
                required_params=["url", "selectors"],
            ),
            ToolDefinition(
                name="search_page",
                description="Search for specific text within a web page and return matching contexts.",
                parameters={
                    "url": {
                        "type": "string",
                        "description": "URL to search within",
                    },
                    "query": {
                        "type": "string",
                        "description": "Text to search for in the page content",
                    },
                },
                required_params=["url", "query"],
            ),
        ],
        retry_policy=RetryPolicy(max_retries=2, base_delay_seconds=1.0),
        tags=["browser", "scraping", "automation", "web"],
        max_concurrent=3,
        timeout_seconds=45.0,
    )

    def __init__(
        self,
        action_registry: BrowserActionRegistry | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._action_registry = action_registry or BrowserActionRegistry()

    async def setup(self) -> None:
        await super().setup()
        if not self._action_registry.available:
            default_provider = HttpxBrowserProvider()
            self._action_registry.register(default_provider, default=True)
        logger.info(
            "browser_agent_setup",
            providers=self._action_registry.available,
        )

    async def teardown(self) -> None:
        await self._action_registry.close_all()
        await super().teardown()

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

        llm_request = LLMRequest(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a browser automation assistant. Use the available tools "
                        "to fulfill the user's web browsing or data extraction request. "
                        "Always use a tool call. Extract the URL and parameters from the "
                        "user message. If the user doesn't provide a full URL, try to "
                        "construct one (e.g., add https:// prefix). "
                        "For data extraction, suggest appropriate CSS selectors."
                    ),
                },
                {"role": "user", "content": text},
            ],
            tools=self.get_tool_schemas(),
            tool_choice="auto",
            temperature=0.0,
        )

        try:
            llm_response = await self.call_llm(llm_request)
        except Exception as exc:
            return await self._fallback_execution(request, str(exc))

        if llm_response.tool_calls:
            return await self._handle_tool_calls(request, llm_response.tool_calls)

        return AgentResponse(
            workflow_id=request.workflow_id,
            subtask_id=request.subtask_id,
            agent_name=self.name,
            success=True,
            data={"response_text": llm_response.content or "Browser action completed."},
        )

    async def _handle_tool_calls(
        self, request: AgentRequest, tool_calls: list[dict[str, Any]]
    ) -> AgentResponse:
        results: list[dict[str, Any]] = []
        response_parts: list[str] = []

        for tc in tool_calls:
            func = tc.get("function", {})
            name = func.get("name", "")
            try:
                args = json.loads(func.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}

            result = await self._execute_tool(name, args)
            results.append({"tool": name, "result": result})

            if result.get("success"):
                response_parts.append(self._format_result(name, result["data"]))
            else:
                response_parts.append(f"Error: {result.get('error', 'Unknown error')}")

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

    async def _execute_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        provider = self._action_registry.default
        try:
            if name == "fetch_page":
                data = await provider.fetch_page(args.get("url", ""))
                return {"success": True, "data": data}
            elif name == "extract_text":
                data = await provider.extract_text(args.get("url", ""))
                return {"success": True, "data": data}
            elif name == "extract_links":
                data = await provider.extract_links(args.get("url", ""))
                return {"success": True, "data": data}
            elif name == "extract_data":
                data = await provider.extract_data(
                    args.get("url", ""),
                    args.get("selectors", {}),
                )
                return {"success": True, "data": data}
            elif name == "search_page":
                data = await provider.search_page(
                    args.get("url", ""),
                    args.get("query", ""),
                )
                return {"success": True, "data": data}
            else:
                return {"success": False, "error": f"Unknown tool: {name}"}
        except Exception as exc:
            logger.warning("browser_tool_error", tool=name, error=str(exc))
            return {"success": False, "error": str(exc)}

    def _format_result(self, tool_name: str, data: dict[str, Any]) -> str:
        title = data.get("title", "")
        url = data.get("url", "")
        header = f"**{title}**\n{url}" if title else url

        if tool_name == "fetch_page":
            ct = data.get("content_type", "")
            length = data.get("content_length", 0)
            return f"{header}\nStatus: {data.get('status_code', '?')} | Type: {ct} | Size: {length:,} bytes"

        elif tool_name == "extract_text":
            text = data.get("text", "")
            preview = text[:2000] + ("..." if len(text) > 2000 else "")
            return f"{header}\n\n{preview}"

        elif tool_name == "extract_links":
            count = data.get("link_count", 0)
            links = data.get("links", [])[:20]
            lines = [f"  - [{l.get('text', '?')}]({l.get('url', '')})" for l in links]
            suffix = f"\n  ... and {count - 20} more" if count > 20 else ""
            return f"{header}\nFound {count} links:\n" + "\n".join(lines) + suffix

        elif tool_name == "extract_data":
            extracted = data.get("data", {})
            lines = []
            for field, values in extracted.items():
                if values:
                    lines.append(f"  **{field}:** {', '.join(values[:5])}")
                else:
                    lines.append(f"  **{field}:** (no matches)")
            return f"{header}\nExtracted data:\n" + "\n".join(lines)

        elif tool_name == "search_page":
            count = data.get("match_count", 0)
            query = data.get("query", "")
            matches = data.get("matches", [])[:5]
            lines = [f'  ...{m.get("context", "")}...' for m in matches]
            return f'{header}\nSearch "{query}": {count} matches\n' + "\n".join(lines)

        return str(data)

    async def _fallback_execution(self, request: AgentRequest, error: str) -> AgentResponse:
        """Fallback when LLM is unavailable: extract URL from text and fetch."""
        text = request.input_data.get("text", "")
        url = self._extract_url(text)

        if not url:
            return AgentResponse(
                workflow_id=request.workflow_id,
                subtask_id=request.subtask_id,
                agent_name=self.name,
                success=False,
                error=f"Could not extract URL from input. LLM error: {error}",
            )

        provider = self._action_registry.default
        try:
            action = self._guess_action(text)

            if action == "links":
                data = await provider.extract_links(url)
                response_text = self._format_result("extract_links", data)
            elif action == "text":
                data = await provider.extract_text(url)
                response_text = self._format_result("extract_text", data)
            else:
                data = await provider.extract_text(url)
                response_text = self._format_result("extract_text", data)

            return AgentResponse(
                workflow_id=request.workflow_id,
                subtask_id=request.subtask_id,
                agent_name=self.name,
                success=True,
                data={"response_text": response_text, "raw": data},
                metadata={"fallback": True, "llm_error": error},
            )
        except Exception as exc:
            return AgentResponse(
                workflow_id=request.workflow_id,
                subtask_id=request.subtask_id,
                agent_name=self.name,
                success=False,
                error=f"Browser action failed: {exc}",
                metadata={"fallback": True, "llm_error": error},
            )

    @staticmethod
    def _extract_url(text: str) -> str:
        import re

        match = re.search(r"https?://[^\s<>\"']+", text)
        return match.group(0) if match else ""

    @staticmethod
    def _guess_action(text: str) -> str:
        text_lower = text.lower()
        if any(kw in text_lower for kw in ["link", "liên kết", "href", "url list"]):
            return "links"
        if any(kw in text_lower for kw in ["text", "nội dung", "content", "đọc"]):
            return "text"
        return "text"
