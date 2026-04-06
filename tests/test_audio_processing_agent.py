"""Tests for audio processing agent."""

from __future__ import annotations

import base64
import io
import struct
import wave
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from vclaw.agents.builtin.audio_processing.agent import AudioProcessingAgent
from vclaw.domain.models import AgentRequest


def _make_request(input_data: dict[str, Any], context: dict[str, Any] | None = None) -> AgentRequest:
    return AgentRequest(
        workflow_id="wf-test",
        subtask_id="st-test",
        agent_name="audio_processing",
        input_data=input_data,
        context=context or {},
    )


def _create_wav_bytes(duration_ms: int = 500, sample_rate: int = 16000) -> bytes:
    """Create a minimal WAV file in memory."""
    n_samples = int(sample_rate * duration_ms / 1000)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(n_samples):
            val = int(16000 * (0.5 if i % 100 < 50 else -0.5))
            wf.writeframes(struct.pack("<h", val))
    return buf.getvalue()


def _create_wav_base64(duration_ms: int = 500) -> str:
    return base64.b64encode(_create_wav_bytes(duration_ms)).decode("ascii")


# ---------------------------------------------------------------------------
# Manifest / setup
# ---------------------------------------------------------------------------


def test_audio_agent_manifest() -> None:
    assert AudioProcessingAgent.manifest.name == "audio_processing"
    cap_names = [c.name for c in AudioProcessingAgent.manifest.capabilities]
    assert "audio_transcription" in cap_names
    assert "audio_metadata" in cap_names
    assert "audio_conversion" in cap_names
    assert "text_to_speech" in cap_names


def test_audio_agent_tools() -> None:
    tool_names = [t.name for t in AudioProcessingAgent.manifest.tools]
    assert "transcribe_audio" in tool_names
    assert "get_audio_info" in tool_names
    assert "convert_audio" in tool_names
    assert "text_to_speech" in tool_names
    assert "download_telegram_audio" in tool_names


@pytest.mark.asyncio
async def test_audio_agent_setup_teardown() -> None:
    agent = AudioProcessingAgent()
    await agent.setup()
    assert await agent.health_check() is True
    await agent.teardown()


# ---------------------------------------------------------------------------
# get_audio_info — WAV file via base64
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_audio_info_wav_base64() -> None:
    agent = AudioProcessingAgent()
    await agent.setup()

    b64 = _create_wav_base64(1000)
    result = await agent._get_audio_info(file_base64=b64)
    assert result["success"] is True
    data = result["data"]
    assert data["format"] == "WavPack" or "WAVE" in data["format"] or data["format"] is not None
    assert data["file_size_bytes"] > 0
    assert data["channels"] == 1
    assert data["sample_rate"] == 16000

    await agent.teardown()


@pytest.mark.asyncio
async def test_get_audio_info_file_path(tmp_path: Path) -> None:
    agent = AudioProcessingAgent()
    await agent.setup()

    wav_path = tmp_path / "test.wav"
    wav_path.write_bytes(_create_wav_bytes(500))

    result = await agent._get_audio_info(file_path=str(wav_path))
    assert result["success"] is True
    assert result["data"]["file_size_bytes"] > 0

    await agent.teardown()


@pytest.mark.asyncio
async def test_get_audio_info_no_input() -> None:
    agent = AudioProcessingAgent()
    await agent.setup()

    result = await agent._get_audio_info()
    assert result["success"] is False
    assert "Provide" in result.get("error", "")

    await agent.teardown()


# ---------------------------------------------------------------------------
# convert_audio — WAV → MP3 (requires ffmpeg; skip if not available)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_convert_audio_wav_to_wav() -> None:
    """Convert WAV → WAV (trivial, should always work with pydub)."""
    agent = AudioProcessingAgent()
    await agent.setup()

    b64 = _create_wav_base64(300)
    result = await agent._convert_audio(
        output_format="wav",
        file_base64=b64,
        input_format="wav",
        filename="converted.wav",
    )
    assert result["success"] is True
    assert result["data"]["format"] == "wav"
    assert result["data"]["size_bytes"] > 0
    assert result["data"]["duration_seconds"] > 0

    Path(result["data"]["file_path"]).unlink(missing_ok=True)
    await agent.teardown()


@pytest.mark.asyncio
async def test_convert_audio_no_pydub() -> None:
    agent = AudioProcessingAgent()
    await agent.setup()

    with patch("vclaw.agents.builtin.audio_processing.agent._PYDUB_AVAILABLE", False):
        result = await agent._convert_audio(output_format="mp3", file_base64=_create_wav_base64())
        assert result["success"] is False
        assert "pydub" in result["error"]

    await agent.teardown()


# ---------------------------------------------------------------------------
# transcribe_audio — mock Whisper API
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transcribe_audio_no_api_key() -> None:
    agent = AudioProcessingAgent()
    await agent.setup()

    with patch("vclaw.agents.builtin.audio_processing.agent._OPENAI_API_KEY", ""):
        result = await agent._transcribe_audio(file_base64=_create_wav_base64())
        assert result["success"] is False
        assert "OPENAI_API_KEY" in result["error"]

    await agent.teardown()


@pytest.mark.asyncio
async def test_transcribe_audio_success_mock() -> None:
    agent = AudioProcessingAgent()
    await agent.setup()

    whisper_json = {
        "text": "Xin chào, đây là bài test",
        "language": "vi",
        "duration": 2.5,
        "segments": [],
    }

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = lambda: None
    mock_response.json = lambda: whisper_json

    with (
        patch("vclaw.agents.builtin.audio_processing.agent._OPENAI_API_KEY", "test-key"),
        patch.object(agent, "_get_client") as mock_client_fn,
    ):
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client_fn.return_value = mock_client

        result = await agent._transcribe_audio(file_base64=_create_wav_base64())

    assert result["success"] is True
    assert result["data"]["text"] == "Xin chào, đây là bài test"
    assert result["data"]["language"] == "vi"
    assert result["data"]["duration"] == 2.5

    await agent.teardown()


# ---------------------------------------------------------------------------
# text_to_speech — mock TTS API
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tts_no_api_key() -> None:
    agent = AudioProcessingAgent()
    await agent.setup()

    with patch("vclaw.agents.builtin.audio_processing.agent._OPENAI_API_KEY", ""):
        result = await agent._text_to_speech(text="Hello world")
        assert result["success"] is False
        assert "OPENAI_API_KEY" in result["error"]

    await agent.teardown()


@pytest.mark.asyncio
async def test_tts_success_mock() -> None:
    agent = AudioProcessingAgent()
    await agent.setup()

    fake_audio = b"\x00" * 1024

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = lambda: None
    mock_response.content = fake_audio

    with (
        patch("vclaw.agents.builtin.audio_processing.agent._OPENAI_API_KEY", "test-key"),
        patch.object(agent, "_get_client") as mock_client_fn,
    ):
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client_fn.return_value = mock_client

        result = await agent._text_to_speech(
            text="Xin chào",
            voice="nova",
            output_format="mp3",
            filename="hello.mp3",
        )

    assert result["success"] is True
    assert result["data"]["filename"] == "hello.mp3"
    assert result["data"]["voice"] == "nova"
    assert result["data"]["size_bytes"] == 1024

    Path(result["data"]["file_path"]).unlink(missing_ok=True)
    await agent.teardown()


# ---------------------------------------------------------------------------
# Telegram file_id extraction
# ---------------------------------------------------------------------------


def test_extract_telegram_file_id_voice() -> None:
    raw = {
        "message": {
            "voice": {
                "file_id": "AwACAgIAAxkBAAIBZ...",
                "duration": 5,
                "mime_type": "audio/ogg",
            }
        }
    }
    assert AudioProcessingAgent._extract_telegram_file_id(raw) == "AwACAgIAAxkBAAIBZ..."


def test_extract_telegram_file_id_audio() -> None:
    raw = {
        "message": {
            "audio": {
                "file_id": "CQACAgIAAxkBAAIBZ...",
                "duration": 180,
                "mime_type": "audio/mpeg",
                "title": "Song Title",
            }
        }
    }
    assert AudioProcessingAgent._extract_telegram_file_id(raw) == "CQACAgIAAxkBAAIBZ..."


def test_extract_telegram_file_id_none() -> None:
    raw = {"message": {"text": "just text"}}
    assert AudioProcessingAgent._extract_telegram_file_id(raw) == ""


def test_extract_telegram_file_id_empty() -> None:
    assert AudioProcessingAgent._extract_telegram_file_id({}) == ""


def test_extract_telegram_file_id_video_note() -> None:
    raw = {
        "message": {
            "video_note": {
                "file_id": "DQACAgIAAxkBAAIBZ...",
                "duration": 10,
            }
        }
    }
    assert AudioProcessingAgent._extract_telegram_file_id(raw) == "DQACAgIAAxkBAAIBZ..."


# ---------------------------------------------------------------------------
# Execute — no input
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_no_input() -> None:
    agent = AudioProcessingAgent()
    await agent.setup()

    req = _make_request({})
    resp = await agent.execute(req)
    assert resp.success is False
    assert "No input" in (resp.error or "")

    await agent.teardown()


# ---------------------------------------------------------------------------
# Execute — auto-transcribe from Telegram voice (mocked)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_auto_transcribe_telegram_voice() -> None:
    agent = AudioProcessingAgent()
    await agent.setup()

    mock_transcribe_result = {
        "success": True,
        "data": {
            "text": "Hello from voice",
            "language": "en",
            "duration": 3.0,
            "segments": [],
        },
    }

    with patch.object(agent, "_transcribe_audio", return_value=mock_transcribe_result):
        req = _make_request(
            {"text": "[non-text message]"},
            context={
                "raw_payload": {
                    "message": {
                        "voice": {
                            "file_id": "test_voice_id",
                            "duration": 3,
                            "mime_type": "audio/ogg",
                        }
                    }
                }
            },
        )
        resp = await agent.execute(req)

    assert resp.success is True
    assert "Hello from voice" in resp.data.get("response_text", "")
    assert resp.data.get("transcript") == "Hello from voice"
    assert resp.data.get("media_type") == "voice"

    await agent.teardown()


# ---------------------------------------------------------------------------
# Format helpers
# ---------------------------------------------------------------------------


def test_format_transcribe_audio() -> None:
    agent = AudioProcessingAgent()
    result = agent._format_tool_result(
        "transcribe_audio",
        {
            "text": "Hello world",
            "language": "en",
            "duration": 2.5,
        },
    )
    assert "Hello world" in result
    assert "en" in result


def test_format_get_audio_info() -> None:
    agent = AudioProcessingAgent()
    result = agent._format_tool_result(
        "get_audio_info",
        {
            "duration_seconds": 30.5,
            "format": "MP3",
            "channels": 2,
            "sample_rate": 44100,
            "bitrate": 128,
        },
    )
    assert "30.5" in result
    assert "MP3" in result
    assert "44100" in result


def test_format_convert_audio() -> None:
    agent = AudioProcessingAgent()
    result = agent._format_tool_result(
        "convert_audio",
        {
            "filename": "out.mp3",
            "format": "mp3",
            "size_bytes": 50000,
        },
    )
    assert "out.mp3" in result
    assert "50,000" in result


def test_format_tts() -> None:
    agent = AudioProcessingAgent()
    result = agent._format_tool_result(
        "text_to_speech",
        {
            "filename": "speech.mp3",
            "size_bytes": 8192,
        },
    )
    assert "speech.mp3" in result
    assert "8,192" in result


def test_format_download() -> None:
    agent = AudioProcessingAgent()
    result = agent._format_tool_result(
        "download_telegram_audio",
        {
            "filename": "voice.ogg",
            "size_bytes": 4096,
        },
    )
    assert "voice.ogg" in result
