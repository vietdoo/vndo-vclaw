"""Tests for the browser automation agent."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from vclaw.agents.builtin.browser.actions import (
    BrowserActionProvider,
    BrowserActionRegistry,
    HttpxBrowserProvider,
)
from vclaw.agents.builtin.browser.agent import BrowserAgent
from vclaw.domain.models import AgentRequest


def _make_request(**overrides: Any) -> AgentRequest:
    defaults = {
        "workflow_id": "wf-test",
        "subtask_id": "st-test",
        "agent_name": "browser",
        "input_data": {"text": "fetch https://example.com"},
    }
    defaults.update(overrides)
    return AgentRequest(**defaults)


class TestBrowserAgentManifest:
    def test_manifest_name(self) -> None:
        agent = BrowserAgent()
        assert agent.name == "browser"

    def test_manifest_capabilities(self) -> None:
        agent = BrowserAgent()
        cap_names = [c.name for c in agent.manifest.capabilities]
        assert "web_scraping" in cap_names
        assert "web_browsing" in cap_names
        assert "data_extraction" in cap_names
        assert "link_extraction" in cap_names

    def test_manifest_tools(self) -> None:
        agent = BrowserAgent()
        tool_names = [t.name for t in agent.manifest.tools]
        assert "fetch_page" in tool_names
        assert "extract_text" in tool_names
        assert "extract_links" in tool_names
        assert "extract_data" in tool_names
        assert "search_page" in tool_names

    def test_tool_schemas(self) -> None:
        agent = BrowserAgent()
        schemas = agent.get_tool_schemas()
        assert len(schemas) == 5
        for schema in schemas:
            assert schema["type"] == "function"
            assert "name" in schema["function"]
            assert "parameters" in schema["function"]


class TestBrowserActionRegistry:
    def test_register_and_get(self) -> None:
        registry = BrowserActionRegistry()
        provider = HttpxBrowserProvider()
        registry.register(provider, default=True)
        assert registry.get("httpx") is provider
        assert registry.default is provider

    def test_available_providers(self) -> None:
        registry = BrowserActionRegistry()
        provider = HttpxBrowserProvider()
        registry.register(provider)
        assert "httpx" in registry.available

    def test_get_missing_raises(self) -> None:
        registry = BrowserActionRegistry()
        with pytest.raises(KeyError, match="not registered"):
            registry.get("nonexistent")

    def test_first_registered_is_default(self) -> None:
        registry = BrowserActionRegistry()
        provider = HttpxBrowserProvider()
        registry.register(provider)
        assert registry.default is provider


class TestHttpxBrowserProvider:
    def test_name(self) -> None:
        provider = HttpxBrowserProvider()
        assert provider.name == "httpx"

    def test_extract_title(self) -> None:
        html = "<html><head><title>Test Page</title></head></html>"
        assert HttpxBrowserProvider._extract_title(html) == "Test Page"

    def test_extract_title_missing(self) -> None:
        html = "<html><head></head></html>"
        assert HttpxBrowserProvider._extract_title(html) == ""

    def test_css_select_by_tag(self) -> None:
        html = "<p>Hello</p><p>World</p>"
        results = HttpxBrowserProvider._css_select_text(html, "p")
        assert results == ["Hello", "World"]

    def test_css_select_by_class(self) -> None:
        html = '<div class="price">$10</div><div class="other">skip</div>'
        results = HttpxBrowserProvider._css_select_text(html, ".price")
        assert results == ["$10"]

    def test_css_select_by_id(self) -> None:
        html = '<div id="main">Content</div>'
        results = HttpxBrowserProvider._css_select_text(html, "#main")
        assert results == ["Content"]


class TestBrowserAgentSetup:
    async def test_setup_registers_default_provider(self) -> None:
        agent = BrowserAgent()
        await agent.setup()
        assert "httpx" in agent._action_registry.available

    async def test_setup_preserves_custom_registry(self) -> None:
        registry = BrowserActionRegistry()
        mock_provider = AsyncMock(spec=BrowserActionProvider)
        mock_provider.name = "custom"
        registry.register(mock_provider, default=True)

        agent = BrowserAgent(action_registry=registry)
        await agent.setup()
        assert "custom" in agent._action_registry.available


class TestBrowserAgentFallback:
    async def test_fallback_extracts_url(self) -> None:
        agent = BrowserAgent()
        await agent.setup()
        assert agent._extract_url("fetch https://example.com please") == "https://example.com"

    async def test_fallback_no_url(self) -> None:
        agent = BrowserAgent()
        await agent.setup()
        assert agent._extract_url("no url here") == ""

    async def test_guess_action_links(self) -> None:
        assert BrowserAgent._guess_action("get all links from page") == "links"

    async def test_guess_action_text(self) -> None:
        assert BrowserAgent._guess_action("read the content") == "text"

    async def test_guess_action_default(self) -> None:
        assert BrowserAgent._guess_action("something else") == "text"


class TestBrowserAgentExecute:
    async def test_execute_no_text(self) -> None:
        agent = BrowserAgent()
        await agent.setup()
        request = _make_request(input_data={})
        response = await agent.execute(request)
        assert not response.success
        assert "No input text" in (response.error or "")

    async def test_execute_fallback_no_url(self) -> None:
        agent = BrowserAgent()
        await agent.setup()
        request = _make_request(input_data={"text": "do something"})
        response = await agent.execute(request)
        assert not response.success
        assert "Could not extract URL" in (response.error or "")

    async def test_execute_tool_directly(self) -> None:
        agent = BrowserAgent()
        await agent.setup()

        mock_provider = AsyncMock(spec=BrowserActionProvider)
        mock_provider.name = "mock"
        mock_provider.extract_text = AsyncMock(return_value={
            "url": "https://example.com",
            "title": "Example",
            "text": "Hello World",
            "text_length": 11,
        })
        agent._action_registry.register(mock_provider, default=True)

        result = await agent._execute_tool("extract_text", {"url": "https://example.com"})
        assert result["success"]
        assert result["data"]["title"] == "Example"

    async def test_execute_tool_unknown(self) -> None:
        agent = BrowserAgent()
        await agent.setup()
        result = await agent._execute_tool("unknown_tool", {})
        assert not result["success"]
        assert "Unknown tool" in result["error"]
