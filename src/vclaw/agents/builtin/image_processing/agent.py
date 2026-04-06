"""Image processing agent for reading, analyzing, and creating images.

Library selection:
  - Pillow (PIL)  — image read/write, resize, crop, convert, metadata
  - LLM vision    — image analysis/description (via multimodal LLM)

Install:
    pip install Pillow
"""

from __future__ import annotations

import base64
import contextlib
import io
import json
import os
import tempfile
from pathlib import Path
from typing import Any, ClassVar

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

try:
    from PIL import Image, ImageDraw, ImageFont

    _PILLOW_AVAILABLE = True
except ImportError:
    _PILLOW_AVAILABLE = False

_OUTPUT_DIR = os.environ.get("VCLAW_IMAGE_OUTPUT_DIR", tempfile.gettempdir())

_SUPPORTED_READ_FORMATS = {"png", "jpg", "jpeg", "gif", "bmp", "tiff", "tif", "webp", "ico"}
_SUPPORTED_WRITE_FORMATS = {"png", "jpg", "jpeg", "gif", "bmp", "tiff", "webp"}


class ImageProcessingAgent(AgentBase):
    """Agent for reading, analyzing, and creating image files.

    Can extract metadata, resize, crop, convert formats, generate placeholder
    images, and analyze image content via multimodal LLM. All file transport
    uses base64 encoding over the event bus.
    """

    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="image_processing",
        version="0.1.0",
        description=(
            "Processes images: read metadata, resize, crop, rotate, convert formats, "
            "create placeholder images with text, and analyze image content via LLM vision. "
            "Supports PNG, JPEG, GIF, BMP, TIFF, WebP."
        ),
        capabilities=[
            AgentCapability(
                name="image_reading",
                description=(
                    "Read image files and extract metadata (dimensions, format, color mode, file size, EXIF data)."
                ),
            ),
            AgentCapability(
                name="image_analysis",
                description=(
                    "Analyze image content using LLM vision — describe what is in "
                    "the image, extract text (OCR-like), identify objects."
                ),
            ),
            AgentCapability(
                name="image_manipulation",
                description=("Resize, crop, rotate, flip, and convert image formats. Apply basic transformations."),
            ),
            AgentCapability(
                name="image_creation",
                description=(
                    "Create simple images: solid color backgrounds, text overlays, placeholder images with labels."
                ),
            ),
        ],
        tools=[
            ToolDefinition(
                name="get_image_info",
                description="Get metadata about an image (dimensions, format, mode, EXIF)",
                parameters={
                    "file_base64": {
                        "type": "string",
                        "description": "Base64-encoded image content",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Path to image file on disk",
                    },
                },
                required_params=[],
            ),
            ToolDefinition(
                name="analyze_image",
                description=(
                    "Analyze image content using LLM vision — describe what is in the image, "
                    "answer questions about the image"
                ),
                parameters={
                    "file_base64": {
                        "type": "string",
                        "description": "Base64-encoded image content",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Path to image file on disk",
                    },
                    "question": {
                        "type": "string",
                        "description": "Question about the image (default: 'Describe this image in detail')",
                    },
                },
                required_params=[],
            ),
            ToolDefinition(
                name="resize_image",
                description="Resize an image to specified dimensions",
                parameters={
                    "file_base64": {
                        "type": "string",
                        "description": "Base64-encoded image content",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Path to image file on disk",
                    },
                    "width": {"type": "integer", "description": "Target width in pixels"},
                    "height": {"type": "integer", "description": "Target height in pixels"},
                    "keep_aspect_ratio": {
                        "type": "boolean",
                        "description": "Maintain aspect ratio using max dimension (default: true)",
                    },
                    "output_format": {
                        "type": "string",
                        "enum": ["png", "jpeg", "webp"],
                        "description": "Output format (default: png)",
                    },
                    "filename": {"type": "string", "description": "Output filename"},
                },
                required_params=["width", "height"],
            ),
            ToolDefinition(
                name="crop_image",
                description="Crop a region from an image",
                parameters={
                    "file_base64": {
                        "type": "string",
                        "description": "Base64-encoded image content",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Path to image file on disk",
                    },
                    "left": {"type": "integer", "description": "Left edge X coordinate"},
                    "top": {"type": "integer", "description": "Top edge Y coordinate"},
                    "right": {"type": "integer", "description": "Right edge X coordinate"},
                    "bottom": {"type": "integer", "description": "Bottom edge Y coordinate"},
                    "output_format": {"type": "string", "description": "Output format (default: png)"},
                    "filename": {"type": "string", "description": "Output filename"},
                },
                required_params=["left", "top", "right", "bottom"],
            ),
            ToolDefinition(
                name="rotate_image",
                description="Rotate an image by specified degrees",
                parameters={
                    "file_base64": {"type": "string", "description": "Base64-encoded image"},
                    "file_path": {"type": "string", "description": "Path to image file"},
                    "degrees": {"type": "number", "description": "Rotation angle in degrees (counter-clockwise)"},
                    "expand": {
                        "type": "boolean",
                        "description": "Expand canvas to fit rotated image (default: true)",
                    },
                    "output_format": {"type": "string", "description": "Output format (default: png)"},
                    "filename": {"type": "string", "description": "Output filename"},
                },
                required_params=["degrees"],
            ),
            ToolDefinition(
                name="convert_format",
                description="Convert an image to a different format",
                parameters={
                    "file_base64": {"type": "string", "description": "Base64-encoded image"},
                    "file_path": {"type": "string", "description": "Path to image file"},
                    "output_format": {
                        "type": "string",
                        "enum": ["png", "jpeg", "gif", "bmp", "tiff", "webp"],
                        "description": "Target format",
                    },
                    "quality": {
                        "type": "integer",
                        "description": "Quality for lossy formats (1-100, default: 85)",
                    },
                    "filename": {"type": "string", "description": "Output filename"},
                },
                required_params=["output_format"],
            ),
            ToolDefinition(
                name="create_image",
                description=(
                    "Create a simple image with solid background and optional text overlay. "
                    "Useful for placeholders, banners, and simple graphics."
                ),
                parameters={
                    "width": {"type": "integer", "description": "Image width in pixels (default: 800)"},
                    "height": {"type": "integer", "description": "Image height in pixels (default: 600)"},
                    "background_color": {
                        "type": "string",
                        "description": "Background color name or hex code (default: white)",
                    },
                    "text": {"type": "string", "description": "Text to overlay on the image"},
                    "text_color": {
                        "type": "string",
                        "description": "Text color name or hex code (default: black)",
                    },
                    "font_size": {"type": "integer", "description": "Font size in pixels (default: 36)"},
                    "output_format": {"type": "string", "description": "Output format (default: png)"},
                    "filename": {"type": "string", "description": "Output filename"},
                },
                required_params=[],
            ),
        ],
        max_concurrent=5,
        timeout_seconds=120.0,
        retry_policy=RetryPolicy(max_retries=2, base_delay_seconds=1.0),
        tags=["image", "photo", "vision", "manipulation", "creation"],
    )

    async def execute(self, request: AgentRequest) -> AgentResponse:
        """Process image request via LLM tool calling or direct dispatch."""
        text = request.input_data.get("text", "")
        file_base64 = request.input_data.get("file_base64", "")
        file_path = request.input_data.get("file_path", "")

        if not text and not file_base64 and not file_path:
            return AgentResponse(
                workflow_id=request.workflow_id,
                subtask_id=request.subtask_id,
                agent_name=self.name,
                success=False,
                error="No input text or image file provided",
            )

        if (file_base64 or file_path) and not text:
            return await self._direct_image_processing(request, file_base64, file_path)

        try:
            llm_resp = await self.call_llm(
                LLMRequest(
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are an image processing assistant. Use the available tools to "
                                "read, analyze, manipulate, or create images. Always use a tool call.\n"
                                f"Pillow available: {_PILLOW_AVAILABLE}"
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
            return await self._fallback_execution(request, str(exc))

        if llm_resp.tool_calls:
            return await self._handle_tool_calls(request, llm_resp.tool_calls)

        return AgentResponse(
            workflow_id=request.workflow_id,
            subtask_id=request.subtask_id,
            agent_name=self.name,
            success=True,
            data={"response_text": llm_resp.content or "Image operation completed."},
        )

    async def _direct_image_processing(
        self,
        request: AgentRequest,
        file_base64: str,
        file_path: str,
    ) -> AgentResponse:
        """Auto-detect and process when a file is provided without specific instructions."""
        args: dict[str, Any] = {}
        if file_base64:
            args["file_base64"] = file_base64
        if file_path:
            args["file_path"] = file_path

        result = await self._execute_tool("get_image_info", args)
        if result.get("success"):
            return AgentResponse(
                workflow_id=request.workflow_id,
                subtask_id=request.subtask_id,
                agent_name=self.name,
                success=True,
                data={
                    "response_text": self._format_tool_result("get_image_info", result["data"]),
                    "tool_results": [{"tool": "get_image_info", "result": result}],
                },
            )

        return AgentResponse(
            workflow_id=request.workflow_id,
            subtask_id=request.subtask_id,
            agent_name=self.name,
            success=False,
            error=result.get("error", "Failed to process image"),
        )

    async def _handle_tool_calls(self, request: AgentRequest, tool_calls: list[dict[str, Any]]) -> AgentResponse:
        results: list[dict[str, Any]] = []
        response_parts: list[str] = []

        for tc in tool_calls:
            func = tc.get("function", {})
            name = func.get("name", "")
            try:
                args: dict[str, Any] = json.loads(func.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}

            file_base64 = request.input_data.get("file_base64", "")
            file_path = request.input_data.get("file_path", "")
            if file_base64 and "file_base64" not in args:
                args["file_base64"] = file_base64
            if file_path and "file_path" not in args:
                args["file_path"] = file_path

            result = await self._execute_tool(name, args)
            results.append({"tool": name, "result": result})

            if result.get("success"):
                response_parts.append(self._format_tool_result(name, result["data"]))
            else:
                response_parts.append(f"❌ {result.get('error', 'Unknown error')}")

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

    def _format_tool_result(self, tool_name: str, data: Any) -> str:
        if not isinstance(data, dict):
            return str(data)

        if tool_name == "get_image_info":
            parts = [
                "🖼️ Image info:",
                f"  Format: {data.get('format', '?')}",
                f"  Dimensions: {data.get('width', '?')}×{data.get('height', '?')} px",
                f"  Mode: {data.get('mode', '?')}",
                f"  File size: {data.get('file_size_bytes', 0):,} bytes",
            ]
            exif = data.get("exif", {})
            if exif:
                parts.append("  EXIF data:")
                for k, v in list(exif.items())[:10]:
                    parts.append(f"    {k}: {v}")
            return "\n".join(parts)

        if tool_name == "analyze_image":
            return f"🔍 Image analysis:\n{data.get('analysis', '?')}"

        if tool_name in ("resize_image", "crop_image", "rotate_image", "convert_format"):
            fname = data.get("filename", "?")
            w = data.get("width", "?")
            h = data.get("height", "?")
            size = data.get("size_bytes", 0)
            return f"✅ {tool_name.replace('_', ' ').title()}: {fname} ({w}×{h}, {size:,} bytes)"

        if tool_name == "create_image":
            fname = data.get("filename", "?")
            w = data.get("width", "?")
            h = data.get("height", "?")
            return f"✅ Created image: {fname} ({w}×{h})"

        return str(data)

    async def _execute_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        try:
            match name:
                case "get_image_info":
                    return self._get_image_info(**args)
                case "analyze_image":
                    return await self._analyze_image(**args)
                case "resize_image":
                    return self._resize_image(**args)
                case "crop_image":
                    return self._crop_image(**args)
                case "rotate_image":
                    return self._rotate_image(**args)
                case "convert_format":
                    return self._convert_format(**args)
                case "create_image":
                    return self._create_image(**args)
                case _:
                    return {"success": False, "error": f"Unknown tool: {name}"}
        except Exception as exc:
            logger.exception("image_tool_error", tool=name)
            return {"success": False, "error": str(exc)}

    def _resolve_image(self, file_base64: str = "", file_path: str = "") -> Image.Image:
        """Load an image from base64 or file path."""
        if not _PILLOW_AVAILABLE:
            raise RuntimeError("Pillow not installed. Run: pip install Pillow")

        if file_base64:
            return Image.open(io.BytesIO(base64.b64decode(file_base64)))
        if file_path:
            path = Path(file_path)
            if not path.is_file():
                raise FileNotFoundError(f"File not found: {file_path}")
            return Image.open(path)
        raise ValueError("Either file_base64 or file_path must be provided")

    def _save_image(
        self,
        img: Image.Image,
        output_format: str = "png",
        filename: str = "",
        quality: int = 85,
    ) -> dict[str, Any]:
        """Save image and return metadata + base64."""
        fmt = output_format.lower()
        if fmt == "jpg":
            fmt = "jpeg"

        if not filename:
            ext = "jpg" if fmt == "jpeg" else fmt
            filename = f"output.{ext}"

        if fmt == "jpeg" and img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        buf = io.BytesIO()
        save_kwargs: dict[str, Any] = {"format": fmt.upper()}
        if fmt in ("jpeg", "webp"):
            save_kwargs["quality"] = quality
        img.save(buf, **save_kwargs)
        raw_bytes = buf.getvalue()

        output_path = Path(_OUTPUT_DIR) / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(raw_bytes)

        return {
            "filename": filename,
            "file_path": str(output_path),
            "width": img.width,
            "height": img.height,
            "format": fmt,
            "size_bytes": len(raw_bytes),
            "file_base64": base64.b64encode(raw_bytes).decode("ascii"),
        }

    def _get_image_info(
        self,
        file_base64: str = "",
        file_path: str = "",
        **_: Any,
    ) -> dict[str, Any]:
        if not _PILLOW_AVAILABLE:
            return {"success": False, "error": "Pillow not installed. Run: pip install Pillow"}

        img = self._resolve_image(file_base64, file_path)
        info: dict[str, Any] = {
            "format": img.format or "unknown",
            "mode": img.mode,
            "width": img.width,
            "height": img.height,
            "file_size_bytes": len(file_base64) * 3 // 4 if file_base64 else 0,
        }

        if file_path:
            info["file_size_bytes"] = Path(file_path).stat().st_size

        exif_data: dict[str, str] = {}
        raw_exif = img.getexif()
        if raw_exif:
            from PIL.ExifTags import TAGS

            for tag_id, value in raw_exif.items():
                tag_name = TAGS.get(tag_id, str(tag_id))
                with contextlib.suppress(Exception):
                    exif_data[tag_name] = str(value)[:200]
            info["exif"] = exif_data

        img.close()
        return {"success": True, "data": info}

    async def _analyze_image(
        self,
        file_base64: str = "",
        file_path: str = "",
        question: str = "",
        **_: Any,
    ) -> dict[str, Any]:
        """Use multimodal LLM to analyze image content."""
        if not file_base64 and file_path:
            path = Path(file_path)
            if not path.is_file():
                return {"success": False, "error": f"File not found: {file_path}"}
            file_base64 = base64.b64encode(path.read_bytes()).decode("ascii")

        if not file_base64:
            return {"success": False, "error": "No image provided for analysis"}

        if not self._llm_router:
            if _PILLOW_AVAILABLE:
                img = self._resolve_image(file_base64=file_base64)
                basic_info = f"Image: {img.width}x{img.height}, format={img.format}, mode={img.mode}"
                img.close()
                return {
                    "success": True,
                    "data": {
                        "analysis": f"[LLM not available] Basic info: {basic_info}",
                    },
                }
            return {"success": False, "error": "LLM router not available for image analysis"}

        prompt = question or "Describe this image in detail. Include any text visible in the image."

        try:
            llm_resp = await self.call_llm(
                LLMRequest(
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{file_base64}",
                                    },
                                },
                            ],
                        },
                    ],
                    temperature=0.1,
                    max_tokens=2048,
                )
            )
            return {
                "success": True,
                "data": {
                    "analysis": llm_resp.content,
                    "question": prompt,
                },
            }
        except Exception as exc:
            logger.warning("llm_vision_failed", error=str(exc))
            if _PILLOW_AVAILABLE:
                img = self._resolve_image(file_base64=file_base64)
                basic = f"Image: {img.width}x{img.height}, format={img.format}, mode={img.mode}"
                img.close()
                return {
                    "success": True,
                    "data": {"analysis": f"[Vision unavailable] {basic}"},
                }
            return {"success": False, "error": f"Image analysis failed: {exc}"}

    def _resize_image(
        self,
        width: int,
        height: int,
        file_base64: str = "",
        file_path: str = "",
        keep_aspect_ratio: bool = True,
        output_format: str = "png",
        filename: str = "",
        **_: Any,
    ) -> dict[str, Any]:
        if not _PILLOW_AVAILABLE:
            return {"success": False, "error": "Pillow not installed. Run: pip install Pillow"}

        img = self._resolve_image(file_base64, file_path)

        if keep_aspect_ratio:
            img.thumbnail((width, height), Image.Resampling.LANCZOS)
        else:
            img = img.resize((width, height), Image.Resampling.LANCZOS)

        data = self._save_image(img, output_format, filename)
        img.close()
        return {"success": True, "data": data}

    def _crop_image(
        self,
        left: int,
        top: int,
        right: int,
        bottom: int,
        file_base64: str = "",
        file_path: str = "",
        output_format: str = "png",
        filename: str = "",
        **_: Any,
    ) -> dict[str, Any]:
        if not _PILLOW_AVAILABLE:
            return {"success": False, "error": "Pillow not installed. Run: pip install Pillow"}

        img = self._resolve_image(file_base64, file_path)
        cropped = img.crop((left, top, right, bottom))

        data = self._save_image(cropped, output_format, filename)
        img.close()
        cropped.close()
        return {"success": True, "data": data}

    def _rotate_image(
        self,
        degrees: float,
        file_base64: str = "",
        file_path: str = "",
        expand: bool = True,
        output_format: str = "png",
        filename: str = "",
        **_: Any,
    ) -> dict[str, Any]:
        if not _PILLOW_AVAILABLE:
            return {"success": False, "error": "Pillow not installed. Run: pip install Pillow"}

        img = self._resolve_image(file_base64, file_path)
        rotated = img.rotate(degrees, expand=expand, resample=Image.Resampling.BICUBIC)

        data = self._save_image(rotated, output_format, filename)
        img.close()
        rotated.close()
        return {"success": True, "data": data}

    def _convert_format(
        self,
        output_format: str,
        file_base64: str = "",
        file_path: str = "",
        quality: int = 85,
        filename: str = "",
        **_: Any,
    ) -> dict[str, Any]:
        if not _PILLOW_AVAILABLE:
            return {"success": False, "error": "Pillow not installed. Run: pip install Pillow"}

        img = self._resolve_image(file_base64, file_path)
        data = self._save_image(img, output_format, filename, quality)
        img.close()
        return {"success": True, "data": data}

    def _create_image(
        self,
        width: int = 800,
        height: int = 600,
        background_color: str = "white",
        text: str = "",
        text_color: str = "black",
        font_size: int = 36,
        output_format: str = "png",
        filename: str = "",
        **_: Any,
    ) -> dict[str, Any]:
        if not _PILLOW_AVAILABLE:
            return {"success": False, "error": "Pillow not installed. Run: pip install Pillow"}

        img = Image.new("RGB", (width, height), background_color)

        if text:
            draw = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
            except OSError:
                font = ImageFont.load_default()

            bbox = draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            x = (width - text_w) // 2
            y = (height - text_h) // 2
            draw.text((x, y), text, fill=text_color, font=font)

        if not filename:
            ext = "jpg" if output_format.lower() == "jpeg" else output_format.lower()
            filename = f"created.{ext}"

        data = self._save_image(img, output_format, filename)
        img.close()
        return {"success": True, "data": data}

    async def _fallback_execution(self, request: AgentRequest, error: str) -> AgentResponse:
        """Fallback when LLM is unavailable."""
        file_base64 = request.input_data.get("file_base64", "")
        file_path = request.input_data.get("file_path", "")

        if file_base64 or file_path:
            args: dict[str, Any] = {}
            if file_base64:
                args["file_base64"] = file_base64
            if file_path:
                args["file_path"] = file_path

            result = await self._execute_tool("get_image_info", args)
            if result.get("success"):
                return AgentResponse(
                    workflow_id=request.workflow_id,
                    subtask_id=request.subtask_id,
                    agent_name=self.name,
                    success=True,
                    data={
                        "response_text": self._format_tool_result("get_image_info", result["data"]),
                    },
                    metadata={"fallback": True, "llm_error": error},
                )

        return AgentResponse(
            workflow_id=request.workflow_id,
            subtask_id=request.subtask_id,
            agent_name=self.name,
            success=False,
            error=(
                "Supported operations: get image info, analyze, resize, crop, rotate, "
                f"convert format, create image. LLM unavailable: {error}"
            ),
        )
