"""ImageProcessorAgent — analyze images, perform OCR, inspect metadata, and resize/convert.

Library availability is checked at import time with graceful degradation:
  - Pillow (PIL)  : image open / resize / convert / basic metadata (pip install Pillow)
  - pytesseract   : OCR text extraction  (pip install pytesseract + apt-get install tesseract-ocr)
  - Vision LLM    : advanced analysis and description via the shared LLM router (model must support vision)

Supported operations
--------------------
  analyze_image     — describe image content using a vision-capable LLM
  extract_text_ocr  — run Tesseract OCR to pull text from an image
  get_metadata      — return dimensions, format, mode, EXIF data
  resize_image      — resize an image and save to disk
  convert_image     — convert between formats (PNG ↔ JPEG ↔ WEBP, etc.)
  describe_url      — fetch an image from a URL and describe it via vision LLM
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import urlparse

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

# ---------------------------------------------------------------------------
# Optional-dependency feature flags
# ---------------------------------------------------------------------------

try:
    from PIL import ExifTags as _ExifTags
    from PIL import Image as _PIL_Image

    _PILLOW_AVAILABLE = True
except ImportError:
    _PILLOW_AVAILABLE = False
    logger.info("pillow_not_installed", hint="pip install Pillow")

try:
    import pytesseract as _pytesseract  # noqa: F401

    _TESSERACT_AVAILABLE = True
except ImportError:
    _TESSERACT_AVAILABLE = False
    logger.info("pytesseract_not_installed", hint="pip install pytesseract")

# Maximum image bytes sent to vision LLM (base64 encoded; ~3 MB raw → ~4 MB b64)
_MAX_IMAGE_BYTES = 3 * 1024 * 1024
# Default output directory for generated/converted files
_DEFAULT_OUTPUT_DIR = "/tmp/vclaw_images"

_SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".tif"}


def _ensure_output_dir(directory: str = _DEFAULT_OUTPUT_DIR) -> Path:
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _image_to_base64(file_path: str) -> tuple[str, str]:
    """Return (base64_data_uri, mime_type) for the image at *file_path*."""
    suffix = Path(file_path).suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }
    mime = mime_map.get(suffix, "image/jpeg")
    with open(file_path, "rb") as fh:
        data = fh.read()
    if len(data) > _MAX_IMAGE_BYTES:
        raise ValueError(
            f"Image too large for vision LLM ({len(data) // 1024} KB). "
            f"Max: {_MAX_IMAGE_BYTES // 1024} KB. Resize the image first."
        )
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}", mime


class ImageProcessorAgent(AgentBase):
    """Agent that analyzes, describes, OCR-scans, and converts image files.

    Vision analysis uses the shared LLM router — the configured model must support
    image inputs (e.g. GPT-4o, Claude 3, Gemini Pro Vision). OCR via Tesseract
    works without an LLM.

    File operations (resize, convert) use Pillow and write output to the
    configured output directory.
    """

    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="image_processor",
        version="0.1.0",
        description=(
            "Image processing agent: describes and analyzes images via vision LLM, "
            "extracts text with OCR (Tesseract), reads image metadata (EXIF), "
            "resizes and converts images between formats. "
            "Supports local files and remote URLs. Handles Vietnamese text in images."
        ),
        capabilities=[
            AgentCapability(
                name="image_analysis",
                description=(
                    "Analyze and describe image content using a vision-capable LLM. "
                    "Supports reading text, identifying objects, scenes, people, charts, and diagrams."
                ),
            ),
            AgentCapability(
                name="ocr",
                description="Extract text from images using Tesseract OCR engine (no LLM required)",
            ),
            AgentCapability(
                name="image_metadata",
                description="Read image dimensions, format, colour mode, and EXIF metadata",
            ),
            AgentCapability(
                name="image_editing",
                description="Resize images and convert between formats (PNG, JPEG, WEBP, BMP, TIFF)",
            ),
        ],
        tools=[
            ToolDefinition(
                name="analyze_image",
                description=(
                    "Send a local image file to the vision LLM and return a description. "
                    "Can answer questions about the image content."
                ),
                parameters={
                    "file_path": {"type": "string", "description": "Absolute path to the image file"},
                    "question": {
                        "type": "string",
                        "description": (
                            "Optional question or instruction for the vision LLM "
                            "(e.g. 'What text is visible?', 'Describe the chart data'). "
                            "Default: general description."
                        ),
                    },
                    "language": {
                        "type": "string",
                        "description": "Language for the response (e.g. 'Vietnamese', 'English'). Default: auto.",
                    },
                },
                required_params=["file_path"],
            ),
            ToolDefinition(
                name="extract_text_ocr",
                description="Extract all visible text from an image using Tesseract OCR (no LLM needed).",
                parameters={
                    "file_path": {"type": "string", "description": "Absolute path to the image file"},
                    "lang": {
                        "type": "string",
                        "description": (
                            "Tesseract language code(s), e.g. 'eng', 'vie', 'eng+vie'. "
                            "Requires corresponding tessdata packages. Default: 'eng'."
                        ),
                    },
                },
                required_params=["file_path"],
            ),
            ToolDefinition(
                name="get_metadata",
                description="Return image dimensions, format, colour mode, and EXIF data.",
                parameters={
                    "file_path": {"type": "string", "description": "Absolute path to the image file"},
                },
                required_params=["file_path"],
            ),
            ToolDefinition(
                name="resize_image",
                description="Resize an image to specified dimensions and save it to disk.",
                parameters={
                    "file_path": {"type": "string", "description": "Absolute path to the source image"},
                    "width": {"type": "integer", "description": "Target width in pixels"},
                    "height": {"type": "integer", "description": "Target height in pixels"},
                    "keep_aspect_ratio": {
                        "type": "boolean",
                        "description": "Maintain aspect ratio (width takes priority). Default: true.",
                    },
                    "output_filename": {
                        "type": "string",
                        "description": "Output filename. Default: <original>_resized.<ext>",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": f"Output directory (default: {_DEFAULT_OUTPUT_DIR})",
                    },
                },
                required_params=["file_path", "width"],
            ),
            ToolDefinition(
                name="convert_image",
                description="Convert an image to a different format (e.g. PNG → JPEG, JPEG → WEBP).",
                parameters={
                    "file_path": {"type": "string", "description": "Absolute path to the source image"},
                    "target_format": {
                        "type": "string",
                        "enum": ["JPEG", "PNG", "WEBP", "BMP", "TIFF", "GIF"],
                        "description": "Target image format",
                    },
                    "quality": {
                        "type": "integer",
                        "description": "JPEG/WEBP quality 1-95 (default: 85)",
                    },
                    "output_filename": {
                        "type": "string",
                        "description": "Output filename. Default: <original>.<new_ext>",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": f"Output directory (default: {_DEFAULT_OUTPUT_DIR})",
                    },
                },
                required_params=["file_path", "target_format"],
            ),
            ToolDefinition(
                name="describe_url",
                description="Download an image from a URL and describe it using the vision LLM.",
                parameters={
                    "url": {"type": "string", "description": "Public URL of the image"},
                    "question": {
                        "type": "string",
                        "description": "Optional question about the image. Default: general description.",
                    },
                    "language": {
                        "type": "string",
                        "description": "Language for the response. Default: auto.",
                    },
                },
                required_params=["url"],
            ),
        ],
        max_concurrent=3,
        timeout_seconds=90.0,
        retry_policy=RetryPolicy(max_retries=1, base_delay_seconds=2.0),
        tags=["image", "vision", "ocr", "photo", "analyze"],
    )

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._http_client: httpx.AsyncClient | None = None

    async def setup(self) -> None:
        await super().setup()
        self._http_client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "vclaw-image-agent/0.1"},
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
        tool_name: str = request.input_data.get("tool", "")
        tool_args: dict[str, Any] = request.input_data.get("args", {})

        if tool_name and tool_args:
            result = await self._execute_tool(tool_name, tool_args)
            success = result.get("success", False)
            return AgentResponse(
                workflow_id=request.workflow_id,
                subtask_id=request.subtask_id,
                agent_name=self.name,
                success=success,
                data=result.get("data", {}),
                error=result.get("error") if not success else None,
            )

        if not text:
            return AgentResponse(
                workflow_id=request.workflow_id,
                subtask_id=request.subtask_id,
                agent_name=self.name,
                success=False,
                error="No input text or tool/args provided",
            )

        try:
            llm_resp = await self.call_llm(
                LLMRequest(
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are an image processing assistant. "
                                "Use the available tools to analyze, OCR-scan, inspect metadata, "
                                "or transform images as requested by the user. "
                                "Always select and call the most appropriate tool.\n\n"
                                f"Pillow available: {_PILLOW_AVAILABLE}, "
                                f"Tesseract available: {_TESSERACT_AVAILABLE}"
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
            return self._no_llm_response(request, str(exc))

        if llm_resp.tool_calls:
            return await self._dispatch_tool_calls(request, llm_resp.tool_calls)

        return AgentResponse(
            workflow_id=request.workflow_id,
            subtask_id=request.subtask_id,
            agent_name=self.name,
            success=True,
            data={"response_text": llm_resp.content or "Image task completed."},
        )

    # ------------------------------------------------------------------
    # Tool dispatch helpers
    # ------------------------------------------------------------------

    async def _dispatch_tool_calls(
        self, request: AgentRequest, tool_calls: list[dict[str, Any]]
    ) -> AgentResponse:
        tasks = []
        for tc in tool_calls:
            func = tc.get("function", {})
            name = func.get("name", "")
            try:
                args: dict[str, Any] = json.loads(func.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}
            tasks.append(self._execute_tool(name, args))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_data: list[dict[str, Any]] = []
        response_parts: list[str] = []
        overall_success = True

        for tc, result in zip(tool_calls, results, strict=False):
            func = tc.get("function", {})
            name = func.get("name", "")
            if isinstance(result, Exception):
                overall_success = False
                response_parts.append(f"Tool {name} error: {result}")
                continue
            assert isinstance(result, dict)
            success = result.get("success", False)
            if not success:
                overall_success = False
                response_parts.append(f"Tool {name} failed: {result.get('error', '?')}")
            else:
                all_data.append({"tool": name, "data": result.get("data", {})})
                response_parts.append(self._format_result(name, result.get("data", {})))

        return AgentResponse(
            workflow_id=request.workflow_id,
            subtask_id=request.subtask_id,
            agent_name=self.name,
            success=overall_success,
            data={
                "response_text": "\n\n".join(response_parts),
                "tool_results": all_data,
            },
        )

    def _format_result(self, tool_name: str, data: dict[str, Any]) -> str:
        if tool_name in ("analyze_image", "describe_url"):
            description = data.get("description", "")
            source = data.get("file_path") or data.get("url", "")
            return f"🖼️ Image analysis (`{source}`):\n{description}"
        if tool_name == "extract_text_ocr":
            ocr_text = data.get("text", "")
            return f"🔤 OCR result:\n{ocr_text[:1000]}"
        if tool_name == "get_metadata":
            w = data.get("width", "?")
            h = data.get("height", "?")
            fmt = data.get("format", "?")
            mode = data.get("mode", "?")
            return f"📐 Metadata: {w}×{h}px | format={fmt} | mode={mode}"
        if tool_name in ("resize_image", "convert_image"):
            out = data.get("output_path", "")
            size = data.get("size_bytes", "?")
            return f"✅ Output: `{out}` ({size} bytes)"
        return str(data)

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    async def _execute_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        try:
            if name == "analyze_image":
                return await self._analyze_image(args)
            if name == "extract_text_ocr":
                return await asyncio.get_event_loop().run_in_executor(
                    None, self._extract_text_ocr, args
                )
            if name == "get_metadata":
                return await asyncio.get_event_loop().run_in_executor(
                    None, self._get_metadata, args
                )
            if name == "resize_image":
                return await asyncio.get_event_loop().run_in_executor(
                    None, self._resize_image, args
                )
            if name == "convert_image":
                return await asyncio.get_event_loop().run_in_executor(
                    None, self._convert_image, args
                )
            if name == "describe_url":
                return await self._describe_url(args)
            return {"success": False, "error": f"Unknown tool: {name}"}
        except Exception as exc:
            logger.exception("image_tool_error", tool=name)
            return {"success": False, "error": str(exc)}

    # --- Vision LLM analysis ---

    async def _analyze_image(self, args: dict[str, Any]) -> dict[str, Any]:
        file_path: str = args["file_path"]
        question: str = args.get("question", "Describe this image in detail.")
        language: str = args.get("language", "")

        if not os.path.isfile(file_path):
            return {"success": False, "error": f"File not found: {file_path}"}

        if not self._llm_router:
            return {
                "success": False,
                "error": "Vision LLM not available. Configure an LLM router to use analyze_image.",
            }

        try:
            data_uri, _ = await asyncio.get_event_loop().run_in_executor(
                None, _image_to_base64, file_path
            )
        except ValueError as exc:
            return {"success": False, "error": str(exc)}

        lang_note = f" Respond in {language}." if language else ""
        system_prompt = (
            f"You are an expert image analyst.{lang_note} "
            "Provide accurate, detailed, and helpful analysis of the image."
        )

        llm_resp = await self.call_llm(
            LLMRequest(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": question},
                            {"type": "image_url", "image_url": {"url": data_uri}},
                        ],
                    },
                ],
                temperature=0.2,
                max_tokens=1024,
            )
        )

        return {
            "success": True,
            "data": {
                "file_path": file_path,
                "question": question,
                "description": llm_resp.content,
                "llm_model": llm_resp.model,
            },
        }

    async def _describe_url(self, args: dict[str, Any]) -> dict[str, Any]:
        url: str = args["url"]
        question: str = args.get("question", "Describe this image in detail.")
        language: str = args.get("language", "")

        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return {"success": False, "error": f"Invalid URL: {url}"}

        if not self._llm_router:
            return {
                "success": False,
                "error": "Vision LLM not available. Configure an LLM router to use describe_url.",
            }

        # Download image, check size, re-encode as data URI
        client = self._http_client or httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        resp = await client.get(url)
        resp.raise_for_status()
        image_bytes = resp.content

        if len(image_bytes) > _MAX_IMAGE_BYTES:
            return {
                "success": False,
                "error": f"Image too large ({len(image_bytes) // 1024} KB). Max: {_MAX_IMAGE_BYTES // 1024} KB.",
            }

        content_type = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
        b64 = base64.b64encode(image_bytes).decode("ascii")
        data_uri = f"data:{content_type};base64,{b64}"

        lang_note = f" Respond in {language}." if language else ""
        system_prompt = (
            f"You are an expert image analyst.{lang_note} "
            "Provide accurate, detailed, and helpful analysis of the image."
        )

        llm_resp = await self.call_llm(
            LLMRequest(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": question},
                            {"type": "image_url", "image_url": {"url": data_uri}},
                        ],
                    },
                ],
                temperature=0.2,
                max_tokens=1024,
            )
        )

        return {
            "success": True,
            "data": {
                "url": url,
                "question": question,
                "description": llm_resp.content,
                "llm_model": llm_resp.model,
                "image_size_kb": round(len(image_bytes) / 1024, 1),
            },
        }

    # --- Tesseract OCR (synchronous) ---

    def _extract_text_ocr(self, args: dict[str, Any]) -> dict[str, Any]:
        if not _TESSERACT_AVAILABLE:
            return {
                "success": False,
                "error": (
                    "pytesseract not installed. Run: pip install pytesseract\n"
                    "Also install Tesseract engine: apt-get install tesseract-ocr\n"
                    "For Vietnamese OCR: apt-get install tesseract-ocr-vie"
                ),
            }
        if not _PILLOW_AVAILABLE:
            return {"success": False, "error": "Pillow not installed. Run: pip install Pillow"}

        import pytesseract as tess

        file_path: str = args["file_path"]
        lang: str = args.get("lang", "eng")

        if not os.path.isfile(file_path):
            return {"success": False, "error": f"File not found: {file_path}"}

        img = _PIL_Image.open(file_path)
        ocr_text: str = tess.image_to_string(img, lang=lang)

        return {
            "success": True,
            "data": {
                "file_path": file_path,
                "lang": lang,
                "text": ocr_text.strip(),
                "char_count": len(ocr_text.strip()),
            },
        }

    # --- Metadata (synchronous) ---

    def _get_metadata(self, args: dict[str, Any]) -> dict[str, Any]:
        if not _PILLOW_AVAILABLE:
            return {"success": False, "error": "Pillow not installed. Run: pip install Pillow"}

        file_path: str = args["file_path"]
        if not os.path.isfile(file_path):
            return {"success": False, "error": f"File not found: {file_path}"}

        img = _PIL_Image.open(file_path)
        width, height = img.size
        file_stat = os.stat(file_path)

        exif_data: dict[str, Any] = {}
        try:
            raw_exif = img._getexif()  # type: ignore[attr-defined]
            if raw_exif:
                exif_data = {
                    _ExifTags.TAGS.get(k, str(k)): str(v)
                    for k, v in raw_exif.items()
                    if k in _ExifTags.TAGS
                }
        except Exception:
            pass

        return {
            "success": True,
            "data": {
                "file_path": file_path,
                "format": img.format or Path(file_path).suffix.lstrip(".").upper(),
                "mode": img.mode,
                "width": width,
                "height": height,
                "size_bytes": file_stat.st_size,
                "size_kb": round(file_stat.st_size / 1024, 1),
                "exif": exif_data,
            },
        }

    # --- Resize (synchronous) ---

    def _resize_image(self, args: dict[str, Any]) -> dict[str, Any]:
        if not _PILLOW_AVAILABLE:
            return {"success": False, "error": "Pillow not installed. Run: pip install Pillow"}

        file_path: str = args["file_path"]
        width: int = int(args["width"])
        height: int | None = int(args["height"]) if args.get("height") else None
        keep_aspect: bool = bool(args.get("keep_aspect_ratio", True))
        output_dir: str = args.get("output_dir", _DEFAULT_OUTPUT_DIR)
        output_filename: str = args.get("output_filename", "")

        if not os.path.isfile(file_path):
            return {"success": False, "error": f"File not found: {file_path}"}

        img = _PIL_Image.open(file_path)
        orig_w, orig_h = img.size

        if keep_aspect or height is None:
            ratio = width / orig_w
            new_size = (width, max(1, int(orig_h * ratio)))
        else:
            new_size = (width, height)

        resized = img.resize(new_size, _PIL_Image.LANCZOS)  # type: ignore[attr-defined]

        stem = Path(file_path).stem
        suffix = Path(file_path).suffix
        out_name = output_filename or f"{stem}_resized{suffix}"
        out_path = _ensure_output_dir(output_dir) / out_name
        resized.save(str(out_path))

        return {
            "success": True,
            "data": {
                "original_path": file_path,
                "output_path": str(out_path),
                "original_size": f"{orig_w}×{orig_h}",
                "new_size": f"{new_size[0]}×{new_size[1]}",
                "size_bytes": out_path.stat().st_size,
            },
        }

    # --- Convert (synchronous) ---

    def _convert_image(self, args: dict[str, Any]) -> dict[str, Any]:
        if not _PILLOW_AVAILABLE:
            return {"success": False, "error": "Pillow not installed. Run: pip install Pillow"}

        file_path: str = args["file_path"]
        target_format: str = args["target_format"].upper()
        quality: int = int(args.get("quality", 85))
        output_dir: str = args.get("output_dir", _DEFAULT_OUTPUT_DIR)
        output_filename: str = args.get("output_filename", "")

        ext_map = {
            "JPEG": ".jpg",
            "PNG": ".png",
            "WEBP": ".webp",
            "BMP": ".bmp",
            "TIFF": ".tiff",
            "GIF": ".gif",
        }
        ext = ext_map.get(target_format, f".{target_format.lower()}")

        if not os.path.isfile(file_path):
            return {"success": False, "error": f"File not found: {file_path}"}

        img = _PIL_Image.open(file_path)

        # JPEG does not support transparency — convert RGBA → RGB
        if target_format == "JPEG" and img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")

        stem = Path(file_path).stem
        out_name = output_filename or f"{stem}{ext}"
        out_path = _ensure_output_dir(output_dir) / out_name

        save_kwargs: dict[str, Any] = {}
        if target_format in ("JPEG", "WEBP"):
            save_kwargs["quality"] = quality
        if target_format == "PNG":
            save_kwargs["optimize"] = True

        img.save(str(out_path), format=target_format, **save_kwargs)

        return {
            "success": True,
            "data": {
                "original_path": file_path,
                "output_path": str(out_path),
                "target_format": target_format,
                "size_bytes": out_path.stat().st_size,
            },
        }

    # ------------------------------------------------------------------
    # LLM-unavailable fallback
    # ------------------------------------------------------------------

    def _no_llm_response(self, request: AgentRequest, error: str) -> AgentResponse:
        return AgentResponse(
            workflow_id=request.workflow_id,
            subtask_id=request.subtask_id,
            agent_name=self.name,
            success=False,
            error=(
                "LLM is unavailable for intent routing. "
                "Pass 'tool' and 'args' directly in input_data, or ensure an LLM is configured. "
                f"LLM error: {error}"
            ),
        )
