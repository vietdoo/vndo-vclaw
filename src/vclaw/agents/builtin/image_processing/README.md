# ImageProcessingAgent

Read, analyze, manipulate, and create **image files**. Supports PNG, JPEG, GIF, BMP, TIFF, WebP.

## Quick Start

```bash
# Install required library
pip install Pillow
# or
pip install vclaw[images]
```

## Capabilities

| Capability | Description |
|---|---|
| `image_reading` | Read metadata: dimensions, format, color mode, EXIF data |
| `image_analysis` | Analyze image content via LLM vision (describe, OCR, Q&A) |
| `image_manipulation` | Resize, crop, rotate, flip, convert between formats |
| `image_creation` | Create images with solid backgrounds and text overlays |

## Tools Reference

### `get_image_info`

Read image metadata without modifying the file.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `file_base64` | string | no | Base64-encoded image |
| `file_path` | string | no | Path to image on disk |

**Returns:** `format`, `mode`, `width`, `height`, `file_size_bytes`, `exif` (dict of EXIF tags)

### `analyze_image`

Analyze image content using a multimodal LLM (GPT-4V compatible).

| Parameter | Type | Required | Description |
|---|---|---|---|
| `file_base64` | string | no | Base64-encoded image |
| `file_path` | string | no | Path to image on disk |
| `question` | string | no | Question about the image (default: detailed description) |

**LLM required:** Yes (falls back to basic metadata if unavailable)

**Returns:** `analysis` (LLM text response), `question`

### `resize_image`

Resize an image to target dimensions.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `width` | integer | **yes** | Target width in pixels |
| `height` | integer | **yes** | Target height in pixels |
| `file_base64` | string | no | Base64-encoded image |
| `file_path` | string | no | Path to image on disk |
| `keep_aspect_ratio` | boolean | no | Use thumbnail mode — fits within box (default: true) |
| `output_format` | string | no | Output format: `png`, `jpeg`, `webp` (default: `png`) |
| `filename` | string | no | Output filename |

**Returns:** `filename`, `file_path`, `width`, `height`, `format`, `size_bytes`, `file_base64`

### `crop_image`

Crop a rectangular region from an image.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `left` | integer | **yes** | Left X coordinate |
| `top` | integer | **yes** | Top Y coordinate |
| `right` | integer | **yes** | Right X coordinate |
| `bottom` | integer | **yes** | Bottom Y coordinate |
| `file_base64` | string | no | Base64-encoded image |
| `file_path` | string | no | Path to image on disk |
| `output_format` | string | no | Output format (default: `png`) |
| `filename` | string | no | Output filename |

**Returns:** Same as `resize_image`

### `rotate_image`

Rotate an image by a given angle.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `degrees` | number | **yes** | Rotation angle (counter-clockwise) |
| `file_base64` | string | no | Base64-encoded image |
| `file_path` | string | no | Path to image on disk |
| `expand` | boolean | no | Expand canvas to fit rotated image (default: true) |
| `output_format` | string | no | Output format (default: `png`) |
| `filename` | string | no | Output filename |

**Returns:** Same as `resize_image`

### `convert_format`

Convert an image to a different format.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `output_format` | string | **yes** | Target: `png`, `jpeg`, `gif`, `bmp`, `tiff`, `webp` |
| `file_base64` | string | no | Base64-encoded image |
| `file_path` | string | no | Path to image on disk |
| `quality` | integer | no | Quality for lossy formats, 1–100 (default: 85) |
| `filename` | string | no | Output filename |

**Note:** RGBA images are auto-converted to RGB when saving as JPEG.

**Returns:** Same as `resize_image`

### `create_image`

Create a new image with a solid background and optional centered text.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `width` | integer | no | Image width in pixels (default: 800) |
| `height` | integer | no | Image height in pixels (default: 600) |
| `background_color` | string | no | Color name or hex (default: `white`) |
| `text` | string | no | Text to center on the image |
| `text_color` | string | no | Text color name or hex (default: `black`) |
| `font_size` | integer | no | Font size in pixels (default: 36) |
| `output_format` | string | no | Output format (default: `png`) |
| `filename` | string | no | Output filename |

**Font:** Uses DejaVu Sans if available (`/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`), otherwise falls back to Pillow default bitmap font.

**Returns:** Same as `resize_image`

## Architecture

```
input_data
  ├── file_base64 / file_path (no text)  →  auto get_image_info
  └── text (+ optional file)             →  LLM tool calling → tool dispatch
                                             └── fallback: get_image_info if LLM unavailable
```

Tool calls from the LLM automatically inherit `file_base64` / `file_path` from `input_data` if the LLM doesn't include them in the tool arguments.

## Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `VCLAW_IMAGE_OUTPUT_DIR` | `tempfile.gettempdir()` | Output directory for created/modified images |

## Supported Formats

| Format | Read | Write |
|---|---|---|
| PNG | ✅ | ✅ |
| JPEG/JPG | ✅ | ✅ |
| GIF | ✅ | ✅ |
| BMP | ✅ | ✅ |
| TIFF/TIF | ✅ | ✅ |
| WebP | ✅ | ✅ |
| ICO | ✅ | ❌ |

## Testing

```bash
python -m pytest tests/test_image_processing_agent.py -v
```

## Graceful Degradation

Pillow is the only required dependency. If not installed, all tools return a clear error message. The agent registers successfully regardless — it will fail at tool execution time, not at startup.

LLM vision (`analyze_image`) falls back to basic Pillow metadata when the LLM router is not configured or the vision call fails.
