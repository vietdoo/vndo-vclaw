# Browser Agent (`vclaw.agents.builtin.browser`)

Pluggable browser automation agent for web scraping, data extraction, and page interaction.

## Architecture

```
BrowserAgent (AgentBase)
    │
    ├── LLM tool-calling (interprets natural language → browser actions)
    │
    └── BrowserActionRegistry (plug-and-play providers)
            │
            ├── HttpxBrowserProvider (default, lightweight, no JS)
            ├── PlaywrightProvider  (optional, full browser, JS rendering)
            └── [YourProvider]      (custom implementation)
```

## Capabilities

| Capability | Description |
|-----------|-------------|
| `web_scraping` | Fetch and extract data from web pages |
| `web_browsing` | Browse web pages and retrieve content |
| `data_extraction` | Extract structured data using CSS selectors |
| `link_extraction` | Extract and analyze hyperlinks |

## Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `fetch_page` | `url` | Fetch page HTML, title, metadata |
| `extract_text` | `url` | Extract clean text (strips scripts/styles/nav) |
| `extract_links` | `url` | Extract all hyperlinks with anchor text |
| `extract_data` | `url`, `selectors` | Extract structured data via CSS selectors |
| `search_page` | `url`, `query` | Full-text search within a page |

## Default Provider: `HttpxBrowserProvider`

Uses `httpx` for HTTP requests and regex-based HTML parsing. Suitable for static pages.

- Follows redirects (up to 5 hops)
- Configurable timeout and max content length
- Custom User-Agent
- Basic CSS selector support: tag, `.class`, `#id`, `tag.class`
- No JavaScript execution

## Adding a Custom Provider

Implement `BrowserActionProvider` and register it:

```python
from vclaw.agents.builtin.browser.actions import BrowserActionProvider, BrowserActionRegistry

class PlaywrightProvider(BrowserActionProvider):
    @property
    def name(self) -> str:
        return "playwright"

    async def fetch_page(self, url, **kwargs):
        # Use playwright to render page with JS
        ...

    async def extract_data(self, url, selectors, **kwargs):
        ...

    async def extract_links(self, url, **kwargs):
        ...

    async def extract_text(self, url, **kwargs):
        ...

    async def search_page(self, url, query, **kwargs):
        ...

# Register at runtime
registry = BrowserActionRegistry()
registry.register(PlaywrightProvider(), default=True)
agent = BrowserAgent(action_registry=registry)
```

## Registration

### Via entry point (pyproject.toml)

```toml
[project.entry-points."vclaw.agents"]
browser = "vclaw.agents.builtin.browser:BrowserAgent"
```

### Via manual registration

```python
from vclaw.agents.builtin.browser import BrowserAgent
await registry.register(BrowserAgent())
```

## Fallback Behavior

When LLM is unavailable, the agent:
1. Extracts URL from input text using regex
2. Guesses action from keywords (links/text/fetch)
3. Executes with default provider
4. Returns result with `metadata.fallback = True`
