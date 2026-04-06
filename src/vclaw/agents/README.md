# Agents Layer — `vclaw.agents`

This package defines the **agent execution contract**, the **registry** (plugin discovery + lifecycle), and all **built-in agents**. Third-party agents live in `plugins/` or are registered via Python entry points — both paths share the same `AgentBase` interface.

## Package Structure

```
agents/
├── base.py                     # AgentBase abstract class
├── registry.py                 # AgentRegistry: discovery + lifecycle
├── __init__.py
└── builtin/
    ├── task_management/
    │   └── agent.py            # Kanban task board agent
    ├── public_service/
    │   └── agent.py            # Vietnamese government services agent
    ├── browser/
    │   └── agent.py            # Web browsing and scraping agent
    ├── document_processor/
    │   └── agent.py            # PDF / Word / Excel reader and creator
    └── image_processor/
        └── agent.py            # Image analysis, OCR, metadata, resize/convert
```

---

## `base.py` — `AgentBase`

Every agent subclasses `AgentBase`. The base class provides:

| Feature | Implementation |
|---------|---------------|
| **Manifest declaration** | `ClassVar[AgentManifest]` — static metadata for routing, discovery, and tool schemas |
| **Lifecycle hooks** | `setup()` called on registration (initializes semaphore); `teardown()` on deregistration |
| **Execution wrapper** | `run()` applies timeout, concurrency semaphore, OTel span, and structured logging around `execute()` |
| **LLM access** | `call_llm(LLMRequest)` routes through the shared `LLMRouter` |
| **Tool schemas** | `get_tool_schemas()` returns OpenAI-compatible function-calling JSON for the manifest tools |
| **Health check** | `health_check()` returns `True` by default; override for custom readiness logic |

### Execution contract

```python
class MyAgent(AgentBase):
    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="my_agent",
        capabilities=[AgentCapability(name="my_cap", description="...")],
        tools=[ToolDefinition(name="my_tool", description="...", parameters={}, required_params=[])],
    )

    async def execute(self, request: AgentRequest) -> AgentResponse:
        # Core logic goes here
        return AgentResponse(
            workflow_id=request.workflow_id,
            subtask_id=request.subtask_id,
            agent_name=self.name,
            success=True,
            data={"response_text": "..."},
        )
```

### Key invariants

- `execute()` must **never raise** — return `AgentResponse(success=False, error=...)` on failure.
- `execute()` is called inside a timeout controlled by `request.timeout_seconds` (falls back to `manifest.timeout_seconds`).
- The concurrency semaphore (`manifest.max_concurrent`, default 5) is enforced in `run()` automatically.

---

## `registry.py` — `AgentRegistry`

Central registry with three discovery mechanisms (in priority order):

### 1. Entry points (`pyproject.toml`)
```toml
[project.entry-points."vclaw.agents"]
my_agent = "my_package:MyAgent"
```
Run `discover_entrypoints()` at startup to load all registered agents.

### 2. Directory scanning
```python
await registry.discover_directories(["plugins", "my_agents_dir"])
```
Scans each directory for Python packages/modules exporting a concrete `AgentBase` subclass with a `manifest` attribute.

### 3. Manual registration
```python
await registry.register(MyAgent())
```

### Routing APIs

| Method | Signature | Use case |
|--------|-----------|----------|
| `get(name)` | `→ AgentBase | None` | Direct lookup by agent name |
| `find_by_capability(cap)` | `→ list[AgentBase]` | O(1) capability-indexed lookup |
| `health_check_all()` | `→ dict[str, bool]` | Readiness sweep across all agents |

### Events emitted

- `vclaw.agent.registered` — on successful `register()`
- `vclaw.agent.deregistered` — on `deregister()`

---

## Built-in Agents

### `TaskManagementAgent` (`builtin/task_management/agent.py`)

**Purpose:** Kanban task board operations via LLM tool-calling.

**Capabilities:** `task_management`, `task_creation`

**Tools:**

| Tool | Required params | Description |
|------|----------------|-------------|
| `create_task` | `title` | Create new task with priority, assignee, team |
| `update_task` | `task_id` | Patch any field on an existing task |
| `move_task` | `task_id`, `status` | Move between `todo → in_progress → review → done` |
| `list_tasks` | — | Filter by team, status, or assignee |
| `get_task` | `task_id` | Fetch single task details |
| `delete_task` | `task_id` | Remove task from board |

**Fallback:** Keyword-based parsing when LLM is unavailable (Vietnamese + English).

**Storage:** In-memory `TaskStore`. Replace with a DB-backed implementation for production.

---

### `PublicServiceAgent` (`builtin/public_service/agent.py`)

**Purpose:** Vietnamese government service directory — document requirements, fees, processing times, and application tracking.

**Capabilities:** `public_service`, `application_tracking`

**Tools:**

| Tool | Required params | Description |
|------|----------------|-------------|
| `lookup_service` | `service_key` | Get details for `cccd`, `passport`, `business_license`, `land_certificate` |
| `list_services` | — | List all available services |
| `submit_application` | `service_key`, `citizen_id` | Create an application record |
| `check_status` | `application_id` | Retrieve application status |

**Responses:** Bilingual (Vietnamese + English).

**Storage:** In-memory class-level dict. Production deployment should integrate with `dichvucong.gov.vn` APIs.

---

## Creating a New Agent (Step-by-Step)

### Step 1: Create the agent module

```
plugins/
└── my_agent/
    ├── __init__.py    # must export the class
    └── agent.py
```

### Step 2: Implement the class

```python
from vclaw.agents.base import AgentBase
from vclaw.domain.models import AgentCapability, AgentManifest, AgentRequest, AgentResponse
from typing import ClassVar

class MyAgent(AgentBase):
    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="my_agent",
        version="0.1.0",
        description="Brief description for the orchestrator LLM prompt",
        capabilities=[
            AgentCapability(
                name="my_capability",
                description="What this agent can do — used for intent routing",
            ),
        ],
        max_concurrent=5,
        timeout_seconds=30.0,
    )

    async def execute(self, request: AgentRequest) -> AgentResponse:
        text = request.input_data.get("text", "")
        # ... your logic here ...
        return AgentResponse(
            workflow_id=request.workflow_id,
            subtask_id=request.subtask_id,
            agent_name=self.name,
            success=True,
            data={"response_text": "Result here"},
        )
```

### Step 3: Export from `__init__.py`

```python
from .agent import MyAgent

__all__ = ["MyAgent"]
```

### Step 4: Register (choose one)

- **Auto-discovery:** Place the directory in `plugins/` → discovered at startup via `discover_directories`.
- **Entry point:** Add to `pyproject.toml` under `[project.entry-points."vclaw.agents"]` and reinstall.
- **Manual:** `await registry.register(MyAgent())` in your startup code.

---

## Testing an Agent

```python
import asyncio
from vclaw.domain.models import AgentRequest

agent = MyAgent()
asyncio.run(agent.setup())

req = AgentRequest(
    workflow_id="wf-test",
    subtask_id="st-test",
    agent_name="my_agent",
    input_data={"text": "test input"},
)
resp = asyncio.run(agent.run(req))
assert resp.success
print(resp.data)
```

See `tests/test_builtin_agents.py` and `tests/test_agent_registry.py` for full test examples.

---

## `DocumentProcessorAgent` (`builtin/document_processor/agent.py`)

**Purpose:** Read, create, and summarise document files in PDF, Word (.docx), and Excel (.xlsx/.xls) formats. Designed to work with Vietnamese and multilingual content.

### Installation

All backing libraries are optional extras. Install the ones you need:

```bash
# All document libraries at once
pip install "vclaw[documents]"

# Or individually
pip install pypdf          # PDF reading
pip install fpdf2          # PDF creation
pip install python-docx    # Word reading and creation
pip install openpyxl       # Excel reading and creation
```

### Capabilities

| Capability | Description |
|---|---|
| `document_reading` | Extract text and structured data from PDF, Word, and Excel files |
| `document_creation` | Generate new PDF, Word (.docx), and Excel (.xlsx) files |
| `document_summarization` | Read a document and produce an LLM-generated summary |

### Tools

| Tool | Required params | Library needed | Description |
|------|----------------|----------------|-------------|
| `read_pdf` | `file_path` | pypdf | Extract page-by-page text from a PDF |
| `read_word` | `file_path` | python-docx | Extract paragraphs and structure from a .docx |
| `read_excel` | `file_path` | openpyxl | Read rows/sheets from a .xlsx file |
| `create_pdf` | `filename`, `content` | fpdf2 | Generate a simple PDF from text |
| `create_word` | `filename`, `sections` | python-docx | Generate a .docx with headings and paragraphs |
| `create_excel` | `filename`, `rows` | openpyxl | Generate a .xlsx from 2-D row data |
| `summarize_document` | `file_path` | any reader + LLM | Read any supported file and return an LLM summary |

### Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `output_dir` per-tool | `/tmp/vclaw_documents` | Directory where generated files are written |
| `max_pages` (read_pdf) | all | Limit pages read from large PDFs |
| `max_rows` (read_excel) | 100 | Limit rows read per sheet |
| `language` (summarize) | auto | Language for LLM summary response |
| `focus` (summarize) | — | Focus area for the summary (e.g. "financial figures") |

### Direct tool dispatch (without LLM routing)

Pass `tool` and `args` directly in `input_data` to bypass LLM intent classification:

```python
from vclaw.domain.models import AgentRequest

req = AgentRequest(
    workflow_id="wf-1",
    subtask_id="st-1",
    agent_name="document_processor",
    input_data={
        "tool": "read_pdf",
        "args": {"file_path": "/path/to/report.pdf", "max_pages": 5},
    },
)
resp = await agent.run(req)
print(resp.data["text"])
```

### Excel creation example

```python
req = AgentRequest(
    workflow_id="wf-2",
    subtask_id="st-2",
    agent_name="document_processor",
    input_data={
        "tool": "create_excel",
        "args": {
            "filename": "sales.xlsx",
            "headers": ["Product", "Q1", "Q2", "Q3"],
            "rows": [
                ["Widget A", 1200, 1450, 1600],
                ["Widget B", 800, 950, 1100],
            ],
            "sheet_name": "Sales",
        },
    },
)
```

### Notes

- Extracting Vietnamese diacritics from PDFs works best when the PDF uses embedded Unicode fonts (not scanned images). For scanned PDFs use `summarize_document` with a vision-capable LLM or the `ImageProcessorAgent` OCR tool.
- `create_pdf` uses FPDF2's built-in Helvetica font which covers basic Latin characters. For full Unicode (Vietnamese diacritics) in generated PDFs, install a TTF font and override the agent's `_create_pdf` method to call `pdf.add_font(...)`.
- Storage is file-system based. For production deployments replace `_DEFAULT_OUTPUT_DIR` with an object-store path (S3, GCS, etc.).

---

## `ImageProcessorAgent` (`builtin/image_processor/agent.py`)

**Purpose:** Analyze and describe image content via a vision-capable LLM, extract visible text with Tesseract OCR, read EXIF metadata, and perform basic image editing (resize, format conversion). Supports local files and remote image URLs.

### Installation

```bash
# All image libraries at once
pip install "vclaw[images]"

# Or individually
pip install Pillow           # Required for resize, convert, metadata, and OCR pre-processing
pip install pytesseract      # OCR wrapper (also needs system Tesseract)

# System Tesseract (Ubuntu/Debian)
apt-get install tesseract-ocr

# Vietnamese OCR language pack
apt-get install tesseract-ocr-vie

# English + Vietnamese together
# Use lang="eng+vie" in extract_text_ocr
```

### Capabilities

| Capability | Description |
|---|---|
| `image_analysis` | Describe image content, answer questions about an image using a vision LLM |
| `ocr` | Extract text from images using Tesseract (no LLM needed) |
| `image_metadata` | Return dimensions, colour mode, format, and EXIF data |
| `image_editing` | Resize images and convert between formats |

### Tools

| Tool | Required params | Library needed | Description |
|------|----------------|----------------|-------------|
| `analyze_image` | `file_path` | Pillow + vision LLM | Describe / query a local image file |
| `extract_text_ocr` | `file_path` | Pillow + pytesseract | OCR text extraction from an image |
| `get_metadata` | `file_path` | Pillow | Image dimensions, format, mode, EXIF |
| `resize_image` | `file_path`, `width` | Pillow | Resize image (aspect-ratio-aware by default) |
| `convert_image` | `file_path`, `target_format` | Pillow | Convert image format (PNG/JPEG/WEBP/BMP/TIFF) |
| `describe_url` | `url` | httpx + vision LLM | Download and describe a remote image |

### Vision LLM requirement

`analyze_image` and `describe_url` require a vision-capable LLM model configured in the LLM router. Supported models include:

- **OpenAI**: `gpt-4o`, `gpt-4-vision-preview`
- **Anthropic (via OpenRouter)**: `claude-3-opus`, `claude-3-sonnet`, `claude-3-haiku`
- **Google (via OpenRouter)**: `gemini-1.5-pro`, `gemini-pro-vision`
- Any other OpenAI-compatible vision endpoint

The agent sends images as base64-encoded `data:image/...;base64,...` URLs in the message content. Maximum image size: **3 MB** (before base64 encoding).

### Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `output_dir` | `/tmp/vclaw_images` | Directory for resize/convert output |
| `language` (analyze/describe) | auto | Language for LLM description response |
| `question` (analyze/describe) | "Describe this image in detail." | Prompt sent alongside the image |
| `lang` (OCR) | `eng` | Tesseract language code(s). Use `eng+vie` for English + Vietnamese |
| `keep_aspect_ratio` (resize) | `true` | Maintain original aspect ratio when resizing |
| `quality` (convert) | 85 | JPEG/WEBP output quality (1–95) |

### Direct tool dispatch example

```python
from vclaw.domain.models import AgentRequest

# OCR on a Vietnamese document scan
req = AgentRequest(
    workflow_id="wf-1",
    subtask_id="st-1",
    agent_name="image_processor",
    input_data={
        "tool": "extract_text_ocr",
        "args": {"file_path": "/path/to/scan.png", "lang": "vie"},
    },
)
resp = await agent.run(req)
print(resp.data["text"])
```

```python
# Vision analysis with a specific question
req = AgentRequest(
    workflow_id="wf-2",
    subtask_id="st-2",
    agent_name="image_processor",
    input_data={
        "tool": "analyze_image",
        "args": {
            "file_path": "/path/to/chart.png",
            "question": "What are the key data points shown in this chart?",
            "language": "Vietnamese",
        },
    },
)
resp = await agent.run(req)
print(resp.data["description"])
```

```python
# Convert PNG to WEBP with quality 90
req = AgentRequest(
    workflow_id="wf-3",
    subtask_id="st-3",
    agent_name="image_processor",
    input_data={
        "tool": "convert_image",
        "args": {
            "file_path": "/path/to/photo.png",
            "target_format": "WEBP",
            "quality": 90,
        },
    },
)
resp = await agent.run(req)
print(resp.data["output_path"])
```

### Notes

- All four operation types (analyze, OCR, metadata, edit) degrade gracefully when a library is missing: a clear error message with the install command is returned instead of raising an exception.
- The `analyze_image` tool sends the raw image bytes encoded as a base64 data URI. Ensure the configured LLM supports the `image_url` content-part format (OpenAI Chat Completions v1 vision spec).
- For large images intended only for OCR, resize first with `resize_image` to speed up Tesseract processing and reduce memory usage.
- EXIF data extraction is best-effort: only JPEG and TIFF files typically carry EXIF. PNG and WEBP may return an empty `exif` dict.
