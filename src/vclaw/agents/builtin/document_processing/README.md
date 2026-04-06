# DocumentProcessingAgent

Read and create **PDF**, **DOCX** (Word), and **XLSX** (Excel) document files.

## Quick Start

```bash
# Install required libraries
pip install pypdf python-docx openpyxl reportlab
# or
pip install vclaw[documents]
```

## Capabilities

| Capability | Description |
|---|---|
| `document_reading` | Extract text from PDF, DOCX, XLSX files |
| `document_creation` | Create new PDF, DOCX, XLSX from structured data |
| `document_info` | Get metadata (page count, sheet names, author, etc.) |

## Tools Reference

### `read_pdf`

Extract text content from a PDF file.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `file_base64` | string | no | Base64-encoded PDF content |
| `file_path` | string | no | Path to PDF on disk |
| `page_numbers` | int[] | no | Specific pages (0-indexed). Empty = all pages |

**Library:** `pypdf`

**Returns:** `text`, `page_count`, `pages_read`, `metadata`, `word_count`

### `read_docx`

Extract paragraphs and tables from a Word document.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `file_base64` | string | no | Base64-encoded DOCX content |
| `file_path` | string | no | Path to DOCX on disk |
| `include_tables` | boolean | no | Extract tables (default: true) |

**Library:** `python-docx`

**Returns:** `text`, `paragraph_count`, `tables`, `table_count`, `metadata`, `word_count`

### `read_xlsx`

Read data from an Excel spreadsheet.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `file_base64` | string | no | Base64-encoded XLSX content |
| `file_path` | string | no | Path to XLSX on disk |
| `sheet_name` | string | no | Sheet to read (default: first sheet) |
| `max_rows` | integer | no | Maximum rows to read (default: 500) |

**Library:** `openpyxl`

**Returns:** `sheet_name`, `sheet_names`, `headers`, `rows`, `row_count`, `column_count`, `preview_rows`

### `create_pdf`

Create a new PDF file.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `content` | string | **yes** | Text content (newlines = paragraph breaks) |
| `title` | string | no | Document title (rendered as bold heading) |
| `filename` | string | no | Output filename (default: `output.pdf`) |

**Library:** `reportlab`

**Returns:** `filename`, `file_path`, `size_bytes`, `file_base64`

### `create_docx`

Create a new Word document.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `content` | string | **yes** | Text content (newlines = paragraphs) |
| `title` | string | no | Document title (rendered as Heading 0) |
| `sections` | object[] | no | Structured sections: `[{"heading": "...", "body": "..."}]` |
| `filename` | string | no | Output filename (default: `output.docx`) |

**Library:** `python-docx`

**Returns:** `filename`, `file_path`, `size_bytes`, `file_base64`

### `create_xlsx`

Create a new Excel spreadsheet.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `headers` | string[] | **yes** | Column headers |
| `rows` | any[][] | **yes** | Data rows (array of arrays) |
| `title` | string | no | Sheet name (default: `Sheet1`) |
| `filename` | string | no | Output filename (default: `output.xlsx`) |

**Library:** `openpyxl`

**Returns:** `filename`, `file_path`, `size_bytes`, `file_base64`

### `get_document_info`

Get metadata about a document file.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `file_type` | string | **yes** | `pdf`, `docx`, or `xlsx` |
| `file_base64` | string | no | Base64-encoded file |
| `file_path` | string | no | Path to file on disk |

**Returns (by type):**
- PDF: `page_count`, `title`, `author`, `encrypted`
- DOCX: `paragraph_count`, `table_count`, `title`, `author`
- XLSX: `sheet_count`, `sheets` (with `max_row`, `max_column` per sheet)

## Architecture

```
input_data
  ├── file_base64 / file_path  →  direct dispatch (auto-detect type → read)
  └── text                     →  LLM tool calling → tool dispatch
                                  └── fallback (keyword match) if LLM unavailable
```

All file I/O is synchronous (bytes in memory). Files are resolved from either `file_base64` or `file_path` via `_resolve_file()`. Created files are saved to `VCLAW_DOCUMENT_OUTPUT_DIR` and also returned as `file_base64` for event bus transport.

## Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `VCLAW_DOCUMENT_OUTPUT_DIR` | `tempfile.gettempdir()` | Output directory for created files |

## Testing

```bash
python -m pytest tests/test_document_processing_agent.py -v
```

## Graceful Degradation

Each library is imported at module load time with a try/except. If a library is missing, the corresponding tool returns a clear error message telling the user which package to install. The agent itself always registers successfully.

| Library | Used by | Install |
|---|---|---|
| `pypdf` | `read_pdf`, `get_document_info(pdf)` | `pip install pypdf` |
| `python-docx` | `read_docx`, `create_docx`, `get_document_info(docx)` | `pip install python-docx` |
| `openpyxl` | `read_xlsx`, `create_xlsx`, `get_document_info(xlsx)` | `pip install openpyxl` |
| `reportlab` | `create_pdf` | `pip install reportlab` |
