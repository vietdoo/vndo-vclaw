# Agents Layer — `vclaw.agents`

This package defines the **agent execution contract**, the **registry** (plugin discovery + lifecycle), and all **built-in agents**. Third-party agents live in `plugins/` or are registered via Python entry points — both paths share the same `AgentBase` interface.

## Package Structure

```
agents/
├── base.py                     # AgentBase abstract class
├── registry.py                 # AgentRegistry: discovery + lifecycle
├── __init__.py
├── README.md                   # This file
└── builtin/
    ├── task_management/
    │   └── agent.py            # Kanban task board agent
    ├── public_service/
    │   └── agent.py            # Vietnamese government services agent
    ├── browser/
    │   ├── agent.py            # Web browsing and scraping agent
    │   └── README.md
    ├── document_processing/
    │   ├── agent.py            # PDF, DOCX, XLSX read/create agent
    │   └── README.md
    ├── image_processing/
    │   ├── agent.py            # Image read/analyze/create agent
    │   └── README.md
    └── audio_processing/
        ├── agent.py            # Audio transcribe/convert/TTS agent
        └── README.md
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

### `DocumentProcessingAgent` (`builtin/document_processing/agent.py`)

**Purpose:** Read text from and create PDF, DOCX (Word), and XLSX (Excel) files. Files are transported via base64 encoding over the event bus.

**Capabilities:** `document_reading`, `document_creation`, `document_info`

**Dependencies (optional):**

```bash
pip install pypdf python-docx openpyxl reportlab
# or install the optional group:
pip install vclaw[documents]
```

Each library is imported lazily — the agent gracefully degrades and returns clear error messages when a library is missing for a specific operation.

**Tools:**

| Tool | Required params | Description |
|------|----------------|-------------|
| `read_pdf` | — | Extract text from a PDF file (base64 or path). Optionally read specific pages. |
| `read_docx` | — | Extract paragraphs and tables from a DOCX file. |
| `read_xlsx` | — | Read headers and data rows from an XLSX spreadsheet. |
| `create_pdf` | `content` | Create a new PDF with title and text content (reportlab). |
| `create_docx` | `content` | Create a DOCX with optional heading/section structure. |
| `create_xlsx` | `headers`, `rows` | Create an XLSX with column headers and data rows. |
| `get_document_info` | `file_type` | Get metadata: page count, sheet names, author, etc. |

**File input/output:** All tools accept `file_base64` (base64-encoded content) or `file_path` (disk path). Creation tools output both a disk file and `file_base64` in the response for downstream transport.

**Direct dispatch:** When `file_base64` or `file_path` is provided in `input_data`, the agent auto-detects file type and reads it without requiring LLM routing.

**Environment variables:**

| Variable | Default | Description |
|---|---|---|
| `VCLAW_DOCUMENT_OUTPUT_DIR` | system temp dir | Directory for created files |

**Tests:** `tests/test_document_processing_agent.py` (20 tests)

---

### `ImageProcessingAgent` (`builtin/image_processing/agent.py`)

**Purpose:** Read metadata, analyze content (via LLM vision), resize, crop, rotate, convert formats, and create simple images with text.

**Capabilities:** `image_reading`, `image_analysis`, `image_manipulation`, `image_creation`

**Dependencies (optional):**

```bash
pip install Pillow
# or install the optional group:
pip install vclaw[images]
```

**Tools:**

| Tool | Required params | Description |
|------|----------------|-------------|
| `get_image_info` | — | Dimensions, format, color mode, EXIF metadata |
| `analyze_image` | — | LLM vision analysis — describe image, answer questions, OCR-like text extraction |
| `resize_image` | `width`, `height` | Resize with optional aspect ratio preservation |
| `crop_image` | `left`, `top`, `right`, `bottom` | Crop a rectangular region |
| `rotate_image` | `degrees` | Rotate counter-clockwise with optional canvas expansion |
| `convert_format` | `output_format` | Convert between PNG, JPEG, GIF, BMP, TIFF, WebP |
| `create_image` | — | Create solid-color image with optional centered text overlay |

**Supported formats:** PNG, JPEG, GIF, BMP, TIFF, WebP, ICO (read-only)

**LLM Vision:** `analyze_image` sends the image as a base64 data URL to a multimodal LLM (OpenAI GPT-4V compatible). Falls back to basic metadata if vision is unavailable.

**Direct dispatch:** When a file is provided without text instructions, the agent automatically returns image metadata.

**Environment variables:**

| Variable | Default | Description |
|---|---|---|
| `VCLAW_IMAGE_OUTPUT_DIR` | system temp dir | Directory for created/modified images |

**Tests:** `tests/test_image_processing_agent.py` (18 tests)

---

### `AudioProcessingAgent` (`builtin/audio_processing/agent.py`)

**Purpose:** Transcribe speech to text, extract audio metadata, convert between audio formats, and generate speech from text. Natively handles Telegram voice messages by auto-detecting `voice`/`audio` in `raw_payload` and transcribing via OpenAI Whisper.

**Capabilities:** `audio_transcription`, `audio_metadata`, `audio_conversion`, `text_to_speech`

**Dependencies (optional):**

```bash
pip install mutagen pydub
# ffmpeg must be on PATH for format conversion
apt install ffmpeg
# or install the optional group:
pip install vclaw[audio]
```

**Tools:**

| Tool | Required params | Description |
|------|----------------|-------------|
| `transcribe_audio` | — | Transcribe speech via Whisper API. Accepts base64, file path, or Telegram file_id. |
| `get_audio_info` | — | Extract metadata: duration, bitrate, sample rate, codec, tags. |
| `convert_audio` | `output_format` | Convert between MP3, WAV, OGG, FLAC, AAC, M4A (pydub + ffmpeg). |
| `text_to_speech` | `text` | Generate speech via OpenAI TTS API. Multiple voices available. |
| `download_telegram_audio` | `file_id` | Download audio/voice from Telegram Bot API. |

**Telegram voice auto-detection:** When `raw_payload` contains `message.voice` or `message.audio`, the agent automatically extracts `file_id`, downloads the file, and transcribes it — no LLM routing needed.

**Environment variables:**

| Variable | Default | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | Required for downloading Telegram files |
| `OPENAI_API_KEY` | — | Required for Whisper and TTS |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible API base URL |
| `VCLAW_WHISPER_MODEL` | `whisper-1` | Whisper model name |
| `VCLAW_TTS_MODEL` | `tts-1` | TTS model name |
| `VCLAW_TTS_VOICE` | `alloy` | Default TTS voice |
| `VCLAW_AUDIO_OUTPUT_DIR` | system temp dir | Output directory for audio files |

**Tests:** `tests/test_audio_processing_agent.py` (24 tests)

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

See `tests/test_builtin_agents.py`, `tests/test_agent_registry.py`, `tests/test_document_processing_agent.py`, `tests/test_image_processing_agent.py`, and `tests/test_audio_processing_agent.py` for full test examples.
