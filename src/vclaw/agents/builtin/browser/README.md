# BrowserAgent — Web Browsing & Automation

The `BrowserAgent` is a **plug-and-play** agent for web browsing, data extraction, and browser automation. It integrates into the Vclaw agent platform as a first-class citizen via the standard `AgentBase` contract.

## Features

| Tool | Description | Requires Playwright |
|------|-------------|-------------------|
| `fetch_page` | Load any URL, return text + links | No (httpx fallback) |
| `extract_data` | Scrape + LLM-powered data extraction | No (httpx fallback) |
| `search_web` | Web search via DuckDuckGo / Bing / Google | No |
| `click_element` | Click a CSS selector on a page | **Yes** |
| `fill_form` | Fill and submit a web form | **Yes** |
| `take_screenshot` | Full-page PNG screenshot (base64) | **Yes** |

## Backend Selection

The agent automatically chooses the best available backend:

```
Playwright installed? ──Yes──► Full browser (JS, screenshots, automation)
         │
         No
         │
         ▼
    httpx fallback  ──► Static HTML + JSON endpoints only
```

No configuration required — the agent detects Playwright at import time.

## Installation

### Minimal (httpx only)
```bash
# Already included in vclaw core dependencies
pip install httpx
```

### Full capability (with Playwright)
```bash
pip install playwright
playwright install chromium
# or for all browsers:
playwright install
```

## Capabilities (for orchestrator routing)

| Capability name | Description |
|----------------|-------------|
| `web_browsing` | Load and read any public web page |
| `web_scraping` | Extract structured data with CSS selectors or LLM |
| `web_automation` | Fill forms, click buttons |
| `screenshot` | Capture full-page screenshots |

## Example Invocations (via Telegram / orchestrator)

```
"Lấy nội dung trang https://vnexpress.net"
→ fetch_page tool → returns title + content + links

"Tìm kiếm giá iPhone 15 trên Google"
→ search_web tool (query="giá iPhone 15", engine="google")

"Chụp screenshot trang https://example.com"
→ take_screenshot tool → returns base64 PNG

"Lấy danh sách tỷ giá từ https://vietcombank.com.vn/exchange-rates"
→ extract_data tool (extraction_prompt="danh sách tỷ giá ngoại tệ")
```

## Direct Usage (without orchestrator)

```python
import asyncio
from vclaw.domain.models import AgentRequest
from vclaw.agents.builtin.browser import BrowserAgent

agent = BrowserAgent()
asyncio.run(agent.setup())

req = AgentRequest(
    workflow_id="test",
    subtask_id="test",
    agent_name="browser",
    input_data={"text": "Fetch https://example.com and summarize the content"},
)
resp = asyncio.run(agent.run(req))
print(resp.data["response_text"])
```

## Registration

### Via entry point (pyproject.toml — already configured)
```toml
[project.entry-points."vclaw.agents"]
browser = "vclaw.agents.builtin.browser:BrowserAgent"
```

### Via plugins/ directory
```
plugins/
└── browser/
    ├── __init__.py    # from vclaw.agents.builtin.browser import BrowserAgent; __all__ = ["BrowserAgent"]
    └── agent.py       # or your custom subclass
```

### Manual
```python
from vclaw.agents.builtin.browser import BrowserAgent
await registry.register(BrowserAgent())
```

## Configuration (Environment Variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `BROWSER_HEADLESS` | `true` | Headless mode for Playwright |
| `BROWSER_TIMEOUT_MS` | `30000` | Per-action timeout (ms) |
| `BROWSER_USER_AGENT` | Chrome/122 UA | Custom user agent string |
| `BROWSER_PROXY` | — | Proxy URL (e.g. `http://user:pass@host:port`) |

## Extending the BrowserAgent

### Subclass for domain-specific scraping

```python
from vclaw.agents.builtin.browser.agent import BrowserAgent
from vclaw.domain.models import AgentManifest, AgentCapability, AgentRequest, AgentResponse
from typing import ClassVar

class VietnamNewsAgent(BrowserAgent):
    """Specialized scraper for Vietnamese news sites."""

    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="vietnam_news",
        description="Fetches and summarizes Vietnamese news articles",
        capabilities=[
            AgentCapability(name="news_scraping", description="Fetch and summarize Vietnamese news"),
        ],
    )

    async def execute(self, request: AgentRequest) -> AgentResponse:
        url = request.input_data.get("url", "https://vnexpress.net")
        fetch = await self._fetch_page(url)
        if not fetch["success"]:
            return AgentResponse(
                workflow_id=request.workflow_id,
                subtask_id=request.subtask_id,
                agent_name=self.name,
                success=False,
                error=fetch.get("error", "Fetch failed"),
            )
        content = fetch["data"]["content"][:3000]
        # ... summarize with LLM ...
        return AgentResponse(
            workflow_id=request.workflow_id,
            subtask_id=request.subtask_id,
            agent_name=self.name,
            success=True,
            data={"response_text": content},
        )
```

## Security Considerations

- **URL validation:** The agent fetches any URL passed by the LLM. In multi-tenant deployments, consider adding an allow-list or deny-list for internal IP ranges.
- **Credential handling:** The `fill_form` tool can submit credentials. Ensure the orchestrator's LLM prompt does not expose secrets in the Telegram channel.
- **Rate limiting:** External sites may rate-limit the agent's requests. The `RetryPolicy` (1 retry, 2s delay) handles transient failures.
- **Screenshot privacy:** Screenshots may capture sensitive page content. The base64 data is included in `AgentResponse.data` — filter before sending to untrusted channels.
