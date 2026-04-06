"""Audio processing agent for transcription, metadata, format conversion, and TTS.

Designed to handle Telegram voice messages and audio files.

Library selection (graceful degradation):
  - mutagen      — audio metadata extraction (duration, bitrate, codec, tags)
  - pydub        — audio format conversion (requires ffmpeg on PATH)
  - httpx        — download Telegram files, call OpenAI-compatible transcription/TTS APIs

External services (optional):
  - OpenAI Whisper API  — speech-to-text transcription
  - OpenAI TTS API      — text-to-speech generation

Install:
    pip install mutagen pydub
    # For format conversion, ffmpeg must be on PATH:
    # apt install ffmpeg  (or brew install ffmpeg)
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

try:
    import mutagen

    _MUTAGEN_AVAILABLE = True
except ImportError:
    _MUTAGEN_AVAILABLE = False

try:
    from pydub import AudioSegment

    _PYDUB_AVAILABLE = True
except ImportError:
    _PYDUB_AVAILABLE = False


_OUTPUT_DIR = os.environ.get("VCLAW_AUDIO_OUTPUT_DIR", tempfile.gettempdir())
_TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
_OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
_OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
_WHISPER_MODEL = os.environ.get("VCLAW_WHISPER_MODEL", "whisper-1")
_TTS_MODEL = os.environ.get("VCLAW_TTS_MODEL", "tts-1")
_TTS_VOICE = os.environ.get("VCLAW_TTS_VOICE", "alloy")


class AudioProcessingAgent(AgentBase):
    """Agent for audio processing: transcription, metadata, conversion, and TTS.

    Handles Telegram voice messages (OGG/OPUS) and general audio files.
    Downloads files from Telegram via Bot API, transcribes via OpenAI Whisper,
    extracts metadata via mutagen, converts formats via pydub, and generates
    speech via OpenAI TTS.
    """

    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="audio_processing",
        version="0.1.0",
        description=(
            "Processes audio files: transcribe speech to text (Whisper), "
            "get audio metadata (duration, bitrate, codec), convert between formats "
            "(MP3, WAV, OGG, FLAC, AAC), generate speech from text (TTS). "
            "Handles Telegram voice messages and audio files natively."
        ),
        capabilities=[
            AgentCapability(
                name="audio_transcription",
                description=(
                    "Transcribe speech from audio files to text using Whisper. "
                    "Supports Telegram voice messages, MP3, WAV, OGG, FLAC, M4A."
                ),
            ),
            AgentCapability(
                name="audio_metadata",
                description=(
                    "Extract metadata from audio files: duration, bitrate, sample rate, "
                    "channels, codec, and ID3/Vorbis tags."
                ),
            ),
            AgentCapability(
                name="audio_conversion",
                description="Convert audio between formats: MP3, WAV, OGG, FLAC, AAC, M4A.",
            ),
            AgentCapability(
                name="text_to_speech",
                description="Generate speech audio from text using TTS (text-to-speech) API.",
            ),
        ],
        tools=[
            ToolDefinition(
                name="transcribe_audio",
                description=(
                    "Transcribe speech from an audio file to text. Supports Telegram file_id, base64, or file path."
                ),
                parameters={
                    "file_base64": {
                        "type": "string",
                        "description": "Base64-encoded audio content",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Path to audio file on disk",
                    },
                    "telegram_file_id": {
                        "type": "string",
                        "description": "Telegram file_id to download and transcribe",
                    },
                    "language": {
                        "type": "string",
                        "description": "Language hint for transcription (ISO 639-1, e.g. 'vi', 'en')",
                    },
                },
                required_params=[],
            ),
            ToolDefinition(
                name="get_audio_info",
                description="Get metadata about an audio file (duration, bitrate, codec, tags)",
                parameters={
                    "file_base64": {
                        "type": "string",
                        "description": "Base64-encoded audio content",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Path to audio file on disk",
                    },
                    "telegram_file_id": {
                        "type": "string",
                        "description": "Telegram file_id to download and inspect",
                    },
                },
                required_params=[],
            ),
            ToolDefinition(
                name="convert_audio",
                description="Convert audio to a different format (requires ffmpeg)",
                parameters={
                    "file_base64": {
                        "type": "string",
                        "description": "Base64-encoded audio content",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Path to audio file on disk",
                    },
                    "telegram_file_id": {
                        "type": "string",
                        "description": "Telegram file_id to download",
                    },
                    "input_format": {
                        "type": "string",
                        "description": "Input format hint (e.g. 'ogg', 'mp3'). Auto-detected if omitted.",
                    },
                    "output_format": {
                        "type": "string",
                        "enum": ["mp3", "wav", "ogg", "flac", "aac", "m4a"],
                        "description": "Target format (default: mp3)",
                    },
                    "bitrate": {
                        "type": "string",
                        "description": "Output bitrate (e.g. '128k', '192k', '320k')",
                    },
                    "filename": {
                        "type": "string",
                        "description": "Output filename",
                    },
                },
                required_params=["output_format"],
            ),
            ToolDefinition(
                name="text_to_speech",
                description="Generate speech audio from text using TTS API",
                parameters={
                    "text": {
                        "type": "string",
                        "description": "Text to convert to speech",
                    },
                    "voice": {
                        "type": "string",
                        "enum": ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
                        "description": "Voice preset (default: alloy)",
                    },
                    "output_format": {
                        "type": "string",
                        "enum": ["mp3", "opus", "aac", "flac", "wav"],
                        "description": "Audio format (default: mp3)",
                    },
                    "speed": {
                        "type": "number",
                        "description": "Playback speed 0.25–4.0 (default: 1.0)",
                    },
                    "filename": {
                        "type": "string",
                        "description": "Output filename",
                    },
                },
                required_params=["text"],
            ),
            ToolDefinition(
                name="download_telegram_audio",
                description="Download an audio/voice file from Telegram by file_id",
                parameters={
                    "file_id": {
                        "type": "string",
                        "description": "Telegram file_id from voice or audio message",
                    },
                    "filename": {
                        "type": "string",
                        "description": "Save as filename (auto-detected if omitted)",
                    },
                },
                required_params=["file_id"],
            ),
        ],
        max_concurrent=3,
        timeout_seconds=120.0,
        retry_policy=RetryPolicy(max_retries=2, base_delay_seconds=2.0),
        tags=["audio", "voice", "transcription", "tts", "telegram", "speech"],
    )

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._http_client: httpx.AsyncClient | None = None

    async def setup(self) -> None:
        await super().setup()
        self._http_client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))

    async def teardown(self) -> None:
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
        return self._http_client

    async def execute(self, request: AgentRequest) -> AgentResponse:
        """Process audio request — auto-detects Telegram voice from raw_payload."""
        text = request.input_data.get("text", "")
        file_base64 = request.input_data.get("file_base64", "")
        file_path = request.input_data.get("file_path", "")
        telegram_file_id = request.input_data.get("telegram_file_id", "")

        raw_payload = request.context.get("raw_payload", {})
        if not telegram_file_id:
            telegram_file_id = self._extract_telegram_file_id(raw_payload)

        if telegram_file_id and (not text or text == "[non-text message]"):
            return await self._auto_transcribe(request, telegram_file_id, raw_payload)

        if (file_base64 or file_path) and (not text or text == "[non-text message]"):
            return await self._direct_audio_processing(request, file_base64, file_path)

        if not text and not file_base64 and not file_path and not telegram_file_id:
            return AgentResponse(
                workflow_id=request.workflow_id,
                subtask_id=request.subtask_id,
                agent_name=self.name,
                success=False,
                error="No input text or audio file provided",
            )

        try:
            llm_resp = await self.call_llm(
                LLMRequest(
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are an audio processing assistant. Use the available tools to "
                                "transcribe, analyze, convert, or generate audio. Always use a tool call.\n"
                                f"Available: mutagen={_MUTAGEN_AVAILABLE}, pydub={_PYDUB_AVAILABLE}\n"
                                "Telegram voice can be handled via telegram_file_id parameter."
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
            data={"response_text": llm_resp.content or "Audio operation completed."},
        )

    @staticmethod
    def _extract_telegram_file_id(raw_payload: dict[str, Any]) -> str:
        """Extract file_id from Telegram voice, audio, or video_note message."""
        message = raw_payload.get("message") or raw_payload.get("edited_message", {})
        for key in ("voice", "audio", "video_note", "document"):
            obj = message.get(key)
            if obj and isinstance(obj, dict):
                file_id = obj.get("file_id", "")
                if file_id:
                    return file_id
        return ""

    async def _auto_transcribe(
        self,
        request: AgentRequest,
        telegram_file_id: str,
        raw_payload: dict[str, Any],
    ) -> AgentResponse:
        """Auto-transcribe when a Telegram voice/audio message is detected."""
        message = raw_payload.get("message") or raw_payload.get("edited_message", {})
        voice = message.get("voice", {})
        audio = message.get("audio", {})
        source_info = voice or audio

        duration = source_info.get("duration", 0)
        mime = source_info.get("mime_type", "audio/ogg")
        media_type = "voice" if voice else "audio"

        result = await self._transcribe_audio(telegram_file_id=telegram_file_id)

        if result.get("success"):
            transcript = result["data"].get("text", "")
            response_text = f"🎤 {media_type.title()} message ({duration}s, {mime})\n📝 Transcription:\n{transcript}"
            return AgentResponse(
                workflow_id=request.workflow_id,
                subtask_id=request.subtask_id,
                agent_name=self.name,
                success=True,
                data={
                    "response_text": response_text,
                    "transcript": transcript,
                    "duration": duration,
                    "mime_type": mime,
                    "media_type": media_type,
                    "telegram_file_id": telegram_file_id,
                },
            )

        return AgentResponse(
            workflow_id=request.workflow_id,
            subtask_id=request.subtask_id,
            agent_name=self.name,
            success=False,
            error=result.get("error", "Transcription failed"),
            data={"telegram_file_id": telegram_file_id, "media_type": media_type},
        )

    async def _direct_audio_processing(
        self,
        request: AgentRequest,
        file_base64: str,
        file_path: str,
    ) -> AgentResponse:
        """Process audio file directly — get info then attempt transcription."""
        args: dict[str, Any] = {}
        if file_base64:
            args["file_base64"] = file_base64
        if file_path:
            args["file_path"] = file_path

        info_result = await self._execute_tool("get_audio_info", args)
        transcribe_result = await self._execute_tool("transcribe_audio", args)

        parts: list[str] = []
        tool_results: list[dict[str, Any]] = []

        if info_result.get("success"):
            parts.append(self._format_tool_result("get_audio_info", info_result["data"]))
            tool_results.append({"tool": "get_audio_info", "result": info_result})

        if transcribe_result.get("success"):
            parts.append(self._format_tool_result("transcribe_audio", transcribe_result["data"]))
            tool_results.append({"tool": "transcribe_audio", "result": transcribe_result})

        if parts:
            return AgentResponse(
                workflow_id=request.workflow_id,
                subtask_id=request.subtask_id,
                agent_name=self.name,
                success=True,
                data={
                    "response_text": "\n\n".join(parts),
                    "tool_results": tool_results,
                },
            )

        error = info_result.get("error", "") or transcribe_result.get("error", "Failed to process audio")
        return AgentResponse(
            workflow_id=request.workflow_id,
            subtask_id=request.subtask_id,
            agent_name=self.name,
            success=False,
            error=error,
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

            for key in ("file_base64", "file_path", "telegram_file_id"):
                val = request.input_data.get(key, "")
                if val and key not in args:
                    args[key] = val

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

        if tool_name == "transcribe_audio":
            text = data.get("text", "")
            lang = data.get("language", "")
            dur = data.get("duration", "")
            parts = ["📝 Transcription:"]
            if lang:
                parts[0] += f" (language: {lang})"
            if dur:
                parts[0] += f" [{dur}s]"
            parts.append(text)
            return "\n".join(parts)

        if tool_name == "get_audio_info":
            parts = [
                "🎵 Audio info:",
                f"  Duration: {data.get('duration_seconds', '?')}s",
                f"  Format: {data.get('format', '?')}",
                f"  Channels: {data.get('channels', '?')}",
                f"  Sample rate: {data.get('sample_rate', '?')} Hz",
                f"  Bitrate: {data.get('bitrate', '?')} kbps",
            ]
            tags = data.get("tags", {})
            if tags:
                parts.append("  Tags:")
                for k, v in list(tags.items())[:10]:
                    parts.append(f"    {k}: {v}")
            return "\n".join(parts)

        if tool_name == "convert_audio":
            fname = data.get("filename", "?")
            size = data.get("size_bytes", 0)
            fmt = data.get("format", "?")
            return f"✅ Converted to {fmt}: {fname} ({size:,} bytes)"

        if tool_name == "text_to_speech":
            fname = data.get("filename", "?")
            size = data.get("size_bytes", 0)
            return f"🔊 Generated speech: {fname} ({size:,} bytes)"

        if tool_name == "download_telegram_audio":
            fname = data.get("filename", "?")
            size = data.get("size_bytes", 0)
            return f"⬇️ Downloaded: {fname} ({size:,} bytes)"

        return str(data)

    async def _execute_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        try:
            match name:
                case "transcribe_audio":
                    return await self._transcribe_audio(**args)
                case "get_audio_info":
                    return await self._get_audio_info(**args)
                case "convert_audio":
                    return await self._convert_audio(**args)
                case "text_to_speech":
                    return await self._text_to_speech(**args)
                case "download_telegram_audio":
                    return await self._download_telegram_audio(**args)
                case _:
                    return {"success": False, "error": f"Unknown tool: {name}"}
        except Exception as exc:
            logger.exception("audio_tool_error", tool=name)
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Telegram file download
    # ------------------------------------------------------------------

    async def _download_telegram_file(self, file_id: str) -> tuple[bytes, str]:
        """Download a file from Telegram Bot API. Returns (bytes, file_path_on_telegram)."""
        token = _TELEGRAM_BOT_TOKEN
        if not token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN not set. Cannot download files from Telegram.")

        client = self._get_client()

        resp = await client.get(f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}")
        resp.raise_for_status()
        result = resp.json().get("result", {})
        tg_file_path = result.get("file_path", "")
        if not tg_file_path:
            raise RuntimeError(f"Telegram returned no file_path for file_id={file_id}")

        file_url = f"https://api.telegram.org/file/bot{token}/{tg_file_path}"
        file_resp = await client.get(file_url)
        file_resp.raise_for_status()

        return file_resp.content, tg_file_path

    async def _resolve_audio_bytes(
        self,
        file_base64: str = "",
        file_path: str = "",
        telegram_file_id: str = "",
    ) -> tuple[bytes, str]:
        """Resolve audio bytes from any source. Returns (bytes, suggested_filename)."""
        if file_base64:
            return base64.b64decode(file_base64), "audio_input"
        if file_path:
            p = Path(file_path)
            if not p.is_file():
                raise FileNotFoundError(f"File not found: {file_path}")
            return p.read_bytes(), p.name
        if telegram_file_id:
            raw, tg_path = await self._download_telegram_file(telegram_file_id)
            return raw, Path(tg_path).name
        raise ValueError("Provide file_base64, file_path, or telegram_file_id")

    # ------------------------------------------------------------------
    # Tool: download_telegram_audio
    # ------------------------------------------------------------------

    async def _download_telegram_audio(
        self,
        file_id: str,
        filename: str = "",
        **_: Any,
    ) -> dict[str, Any]:
        raw, tg_name = await self._download_telegram_file(file_id)

        if not filename:
            filename = tg_name or f"telegram_audio_{file_id[:8]}.ogg"

        output_path = Path(_OUTPUT_DIR) / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(raw)

        return {
            "success": True,
            "data": {
                "filename": filename,
                "file_path": str(output_path),
                "size_bytes": len(raw),
                "file_base64": base64.b64encode(raw).decode("ascii"),
                "telegram_file_id": file_id,
            },
        }

    # ------------------------------------------------------------------
    # Tool: transcribe_audio
    # ------------------------------------------------------------------

    async def _transcribe_audio(
        self,
        file_base64: str = "",
        file_path: str = "",
        telegram_file_id: str = "",
        language: str = "",
        **_: Any,
    ) -> dict[str, Any]:
        """Transcribe audio via OpenAI Whisper API (or compatible)."""
        api_key = _OPENAI_API_KEY
        if not api_key:
            return {
                "success": False,
                "error": (
                    "OPENAI_API_KEY not set. Whisper transcription requires an API key. "
                    "Set OPENAI_API_KEY environment variable."
                ),
            }

        try:
            raw, name = await self._resolve_audio_bytes(file_base64, file_path, telegram_file_id)
        except Exception as exc:
            return {"success": False, "error": str(exc)}

        if not name.endswith((".ogg", ".mp3", ".wav", ".flac", ".m4a", ".webm", ".mp4", ".mpeg", ".mpga")):
            name = f"{name}.ogg"

        client = self._get_client()
        url = f"{_OPENAI_BASE_URL}/audio/transcriptions"

        files = {"file": (name, raw, "application/octet-stream")}
        form_data: dict[str, Any] = {"model": _WHISPER_MODEL}
        if language:
            form_data["language"] = language
        form_data["response_format"] = "verbose_json"

        try:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                files=files,
                data=form_data,
            )
            resp.raise_for_status()
            result = resp.json()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:300]
            return {"success": False, "error": f"Whisper API error ({exc.response.status_code}): {body}"}
        except Exception as exc:
            return {"success": False, "error": f"Whisper API request failed: {exc}"}

        return {
            "success": True,
            "data": {
                "text": result.get("text", ""),
                "language": result.get("language", language),
                "duration": result.get("duration"),
                "segments": result.get("segments", []),
            },
        }

    # ------------------------------------------------------------------
    # Tool: get_audio_info
    # ------------------------------------------------------------------

    async def _get_audio_info(
        self,
        file_base64: str = "",
        file_path: str = "",
        telegram_file_id: str = "",
        **_: Any,
    ) -> dict[str, Any]:
        """Extract audio metadata using mutagen."""
        if not _MUTAGEN_AVAILABLE:
            return {"success": False, "error": "mutagen not installed. Run: pip install mutagen"}

        try:
            raw, name = await self._resolve_audio_bytes(file_base64, file_path, telegram_file_id)
        except Exception as exc:
            return {"success": False, "error": str(exc)}

        tmp_path = Path(_OUTPUT_DIR) / f"_info_{name}"
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_bytes(raw)

        try:
            audio = mutagen.File(str(tmp_path))
            if audio is None:
                return {
                    "success": True,
                    "data": {
                        "format": "unknown",
                        "file_size_bytes": len(raw),
                        "duration_seconds": None,
                        "channels": None,
                        "sample_rate": None,
                        "bitrate": None,
                        "tags": {},
                    },
                }

            info = audio.info if hasattr(audio, "info") else None
            duration = getattr(info, "length", None)
            channels = getattr(info, "channels", None)
            sample_rate = getattr(info, "sample_rate", None)
            bitrate = getattr(info, "bitrate", None)
            if bitrate:
                bitrate = bitrate // 1000

            tags: dict[str, str] = {}
            if hasattr(audio, "tags") and audio.tags:
                for key in list(audio.tags.keys())[:20]:
                    with contextlib.suppress(Exception):
                        tags[str(key)] = str(audio.tags[key])[:200]

            fmt = type(audio).__name__

            return {
                "success": True,
                "data": {
                    "format": fmt,
                    "file_size_bytes": len(raw),
                    "duration_seconds": round(duration, 2) if duration else None,
                    "channels": channels,
                    "sample_rate": sample_rate,
                    "bitrate": bitrate,
                    "tags": tags,
                },
            }
        finally:
            tmp_path.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Tool: convert_audio
    # ------------------------------------------------------------------

    async def _convert_audio(
        self,
        output_format: str = "mp3",
        file_base64: str = "",
        file_path: str = "",
        telegram_file_id: str = "",
        input_format: str = "",
        bitrate: str = "128k",
        filename: str = "",
        **_: Any,
    ) -> dict[str, Any]:
        """Convert audio using pydub (requires ffmpeg)."""
        if not _PYDUB_AVAILABLE:
            return {"success": False, "error": "pydub not installed. Run: pip install pydub"}

        try:
            raw, name = await self._resolve_audio_bytes(file_base64, file_path, telegram_file_id)
        except Exception as exc:
            return {"success": False, "error": str(exc)}

        if not input_format:
            ext = Path(name).suffix.lstrip(".").lower()
            input_format = ext if ext else "ogg"

        try:
            audio = AudioSegment.from_file(io.BytesIO(raw), format=input_format)
        except Exception as exc:
            return {"success": False, "error": f"Failed to decode audio ({input_format}): {exc}"}

        if not filename:
            filename = f"converted.{output_format}"

        buf = io.BytesIO()
        export_params: dict[str, Any] = {"format": output_format}
        if bitrate and output_format in ("mp3", "aac", "ogg", "m4a"):
            export_params["bitrate"] = bitrate

        try:
            audio.export(buf, **export_params)
        except Exception as exc:
            return {"success": False, "error": f"Conversion failed: {exc}. Is ffmpeg installed?"}

        out_bytes = buf.getvalue()
        output_path = Path(_OUTPUT_DIR) / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(out_bytes)

        return {
            "success": True,
            "data": {
                "filename": filename,
                "file_path": str(output_path),
                "format": output_format,
                "size_bytes": len(out_bytes),
                "duration_seconds": round(len(audio) / 1000, 2),
                "file_base64": base64.b64encode(out_bytes).decode("ascii"),
            },
        }

    # ------------------------------------------------------------------
    # Tool: text_to_speech
    # ------------------------------------------------------------------

    async def _text_to_speech(
        self,
        text: str,
        voice: str = "",
        output_format: str = "mp3",
        speed: float = 1.0,
        filename: str = "",
        **_: Any,
    ) -> dict[str, Any]:
        """Generate speech from text via OpenAI TTS API (or compatible)."""
        api_key = _OPENAI_API_KEY
        if not api_key:
            return {
                "success": False,
                "error": "OPENAI_API_KEY not set. TTS requires an API key.",
            }

        client = self._get_client()
        url = f"{_OPENAI_BASE_URL}/audio/speech"

        payload = {
            "model": _TTS_MODEL,
            "input": text,
            "voice": voice or _TTS_VOICE,
            "response_format": output_format,
            "speed": max(0.25, min(4.0, speed)),
        }

        try:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            audio_bytes = resp.content
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:300]
            return {"success": False, "error": f"TTS API error ({exc.response.status_code}): {body}"}
        except Exception as exc:
            return {"success": False, "error": f"TTS API request failed: {exc}"}

        if not filename:
            filename = f"speech.{output_format}"

        output_path = Path(_OUTPUT_DIR) / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(audio_bytes)

        return {
            "success": True,
            "data": {
                "filename": filename,
                "file_path": str(output_path),
                "format": output_format,
                "size_bytes": len(audio_bytes),
                "text_length": len(text),
                "voice": voice or _TTS_VOICE,
                "file_base64": base64.b64encode(audio_bytes).decode("ascii"),
            },
        }

    # ------------------------------------------------------------------
    # Fallback
    # ------------------------------------------------------------------

    async def _fallback_execution(self, request: AgentRequest, error: str) -> AgentResponse:
        """Fallback when LLM is unavailable."""
        telegram_file_id = request.input_data.get("telegram_file_id", "")
        raw_payload = request.context.get("raw_payload", {})
        if not telegram_file_id:
            telegram_file_id = self._extract_telegram_file_id(raw_payload)

        if telegram_file_id:
            return await self._auto_transcribe(request, telegram_file_id, raw_payload)

        file_base64 = request.input_data.get("file_base64", "")
        file_path = request.input_data.get("file_path", "")
        if file_base64 or file_path:
            return await self._direct_audio_processing(request, file_base64, file_path)

        return AgentResponse(
            workflow_id=request.workflow_id,
            subtask_id=request.subtask_id,
            agent_name=self.name,
            success=False,
            error=(
                "Supported operations: transcribe audio, get audio info, convert format, "
                f"text-to-speech. LLM unavailable: {error}"
            ),
        )
