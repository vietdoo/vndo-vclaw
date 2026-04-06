"""Tests for BrowserAgent — uses httpx fallback (no Playwright required)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vclaw.agents.builtin.browser.agent import BrowserAgent, _extract_links, _strip_html_tags
from vclaw.domain.models import AgentRequest

# ── Helpers ─────────────────────────────────────────────────────────────────


def _make_request(text: str = "", **kwargs: object) -> AgentRequest:
    return AgentRequest(
        workflow_id="wf-browser-test",
        subtask_id="st-browser-test",
        agent_name="browser",
        input_data={"text": text, **kwargs},
    )


# ── Unit tests for HTML utilities ───────────────────────────────────────────


def test_strip_html_tags_removes_tags() -> None:
    html = "<html><body><h1>Hello</h1><p>World</p></body></html>"
    result = _strip_html_tags(html)
    assert "Hello" in result
    assert "World" in result
    assert "<" not in result


def test_strip_html_tags_removes_scripts() -> None:
    html = "<html><script>alert('xss')</script><p>Content</p></html>"
    result = _strip_html_tags(html)
    assert "alert" not in result
    assert "Content" in result


def test_strip_html_tags_truncates_long_content() -> None:
    html = "<p>" + "a" * 20000 + "</p>"
    result = _strip_html_tags(html)
    assert len(result) <= 8000


def test_extract_links_absolute() -> None:
    html = '<a href="https://example.com/page">Example</a>'
    links = _extract_links(html, "https://base.com")
    assert len(links) == 1
    assert links[0]["url"] == "https://example.com/page"
    assert links[0]["text"] == "Example"


def test_extract_links_relative() -> None:
    html = '<a href="/about">About</a>'
    links = _extract_links(html, "https://example.com")
    assert links[0]["url"] == "https://example.com/about"


def test_extract_links_limit() -> None:
    html = "".join(f'<a href="https://example.com/{i}">Link {i}</a>' for i in range(50))
    links = _extract_links(html, "https://example.com")
    assert len(links) <= 30


# ── Agent manifest ───────────────────────────────────────────────────────────


def test_manifest_is_valid() -> None:
    assert BrowserAgent.manifest.name == "browser"
    assert BrowserAgent.manifest.capabilities
    assert BrowserAgent.manifest.tools
    cap_names = [c.name for c in BrowserAgent.manifest.capabilities]
    assert "web_browsing" in cap_names
    assert "web_scraping" in cap_names
    assert "web_automation" in cap_names


def test_manifest_tool_names() -> None:
    tool_names = [t.name for t in BrowserAgent.manifest.tools]
    assert "fetch_page" in tool_names
    assert "extract_data" in tool_names
    assert "search_web" in tool_names
    assert "take_screenshot" in tool_names
    assert "click_element" in tool_names
    assert "fill_form" in tool_names


# ── Agent lifecycle ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_setup_creates_http_client() -> None:
    agent = BrowserAgent()
    await agent.setup()
    assert agent._http_client is not None
    await agent.teardown()
    assert agent._http_client is None


# ── Missing input ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_execute_returns_error_for_empty_input() -> None:
    agent = BrowserAgent()
    await agent.setup()

    resp = await agent.execute(_make_request(text=""))
    assert not resp.success
    assert resp.error
    await agent.teardown()


# ── Fallback (no LLM) ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fallback_with_url_in_text() -> None:
    """When LLM is unavailable, agent should directly fetch the URL in the text."""
    agent = BrowserAgent()
    await agent.setup()

    mock_page_data = {
        "url": "https://example.com",
        "title": "Example Domain",
        "content": "This domain is for use in illustrative examples.",
        "links": [],
        "backend": "httpx",
    }

    with patch.object(agent, "_fetch_page", new=AsyncMock(return_value={"success": True, "data": mock_page_data})):
        resp = await agent._fallback_execution(_make_request(text="Fetch https://example.com"), "LLM error")

    assert resp.success
    assert "Example Domain" in resp.data["response_text"]
    assert resp.metadata.get("fallback") is True
    await agent.teardown()


@pytest.mark.asyncio
async def test_fallback_without_url_returns_error() -> None:
    agent = BrowserAgent()
    await agent.setup()

    resp = await agent._fallback_execution(_make_request(text="no url here"), "LLM down")
    assert not resp.success
    assert "LLM" in resp.error
    await agent.teardown()


# ── _fetch_page (httpx backend) ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_httpx_fetch_parses_html() -> None:
    agent = BrowserAgent()
    await agent.setup()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "<html><head><title>Test Page</title></head><body><p>Hello world</p><a href='https://link.com'>Link</a></body></html>"
    mock_resp.url = "https://example.com"
    mock_resp.raise_for_status = MagicMock()

    with patch.object(agent._http_client, "get", new=AsyncMock(return_value=mock_resp)):
        result = await agent._httpx_fetch("https://example.com", include_links=True)

    assert result["success"]
    assert result["data"]["title"] == "Test Page"
    assert "Hello world" in result["data"]["content"]
    assert any(lk["url"] == "https://link.com" for lk in result["data"]["links"])
    await agent.teardown()


# ── search_web ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_web_returns_results() -> None:
    agent = BrowserAgent()
    await agent.setup()

    mock_fetch = {
        "success": True,
        "data": {
            "content": "search results page",
            "links": [
                {"text": "Python docs", "url": "https://docs.python.org"},
                {"text": "Real Python", "url": "https://realpython.com"},
            ],
        },
    }

    with patch.object(agent, "_fetch_page", new=AsyncMock(return_value=mock_fetch)):
        result = await agent._search_web(query="python tutorial", num_results=5)

    assert result["success"]
    data = result["data"]
    assert data["query"] == "python tutorial"
    assert isinstance(data["results"], list)
    await agent.teardown()


# ── extract_data (no LLM) ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_extract_data_without_llm_returns_raw_content() -> None:
    agent = BrowserAgent()
    await agent.setup()

    mock_fetch = {
        "success": True,
        "data": {
            "url": "https://example.com",
            "title": "Example",
            "content": "Product price: $99",
        },
    }

    with patch.object(agent, "_fetch_page", new=AsyncMock(return_value=mock_fetch)):
        result = await agent._extract_data("https://example.com", "product price")

    assert result["success"]
    assert "price" in result["data"]["extracted"].lower() or "[LLM not available]" in result["data"]["extracted"]
    await agent.teardown()


# ── Playwright-only tools return error when not available ────────────────────


@pytest.mark.asyncio
async def test_click_element_returns_error_without_playwright() -> None:
    import vclaw.agents.builtin.browser.agent as browser_module

    agent = BrowserAgent()
    await agent.setup()

    original = browser_module._PLAYWRIGHT_AVAILABLE
    browser_module._PLAYWRIGHT_AVAILABLE = False
    try:
        result = await agent._click_element("https://example.com", "#btn")
    finally:
        browser_module._PLAYWRIGHT_AVAILABLE = original

    assert not result["success"]
    assert "playwright" in result["error"].lower()
    await agent.teardown()


@pytest.mark.asyncio
async def test_fill_form_returns_error_without_playwright() -> None:
    import vclaw.agents.builtin.browser.agent as browser_module

    agent = BrowserAgent()
    await agent.setup()

    original = browser_module._PLAYWRIGHT_AVAILABLE
    browser_module._PLAYWRIGHT_AVAILABLE = False
    try:
        result = await agent._fill_form("https://example.com", {"#email": "test@test.com"})
    finally:
        browser_module._PLAYWRIGHT_AVAILABLE = original

    assert not result["success"]
    assert "playwright" in result["error"].lower()
    await agent.teardown()


@pytest.mark.asyncio
async def test_take_screenshot_returns_error_without_playwright() -> None:
    import vclaw.agents.builtin.browser.agent as browser_module

    agent = BrowserAgent()
    await agent.setup()

    original = browser_module._PLAYWRIGHT_AVAILABLE
    browser_module._PLAYWRIGHT_AVAILABLE = False
    try:
        result = await agent._take_screenshot("https://example.com")
    finally:
        browser_module._PLAYWRIGHT_AVAILABLE = original

    assert not result["success"]
    assert "playwright" in result["error"].lower()
    await agent.teardown()


# ── LLM tool-call dispatch ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_execute_dispatches_tool_calls_from_llm() -> None:
    from vclaw.domain.models import LLMResponse

    agent = BrowserAgent()
    await agent.setup()

    mock_llm_resp = LLMResponse(
        tool_calls=[
            {
                "function": {
                    "name": "fetch_page",
                    "arguments": '{"url": "https://example.com"}',
                }
            }
        ],
        model="gpt-4o-mini",
        provider="openai",
    )
    mock_fetch_result = {
        "success": True,
        "data": {
            "url": "https://example.com",
            "title": "Example",
            "content": "Hello world",
            "links": [],
            "backend": "httpx",
        },
    }

    with (
        patch.object(agent, "call_llm", new=AsyncMock(return_value=mock_llm_resp)),
        patch.object(agent, "_fetch_page", new=AsyncMock(return_value=mock_fetch_result)),
    ):
        resp = await agent.execute(_make_request(text="Fetch example.com"))

    assert resp.success
    assert "Example" in resp.data["response_text"]
    await agent.teardown()
