# AudioProcessingAgent

Transcribe speech, extract metadata, convert formats, and generate speech from text. Native support for **Telegram voice messages** and audio files.

## Quick Start

```bash
# Install required libraries
pip install mutagen pydub
# or
pip install vclaw[audio]

# For format conversion, ffmpeg must be on PATH:
apt install ffmpeg  # Debian/Ubuntu
brew install ffmpeg  # macOS
```

## Capabilities

| Capability | Description |
|---|---|
| `audio_transcription` | Transcribe speech to text via OpenAI Whisper API |
| `audio_metadata` | Extract duration, bitrate, sample rate, codec, ID3/Vorbis tags |
| `audio_conversion` | Convert between MP3, WAV, OGG, FLAC, AAC, M4A (requires ffmpeg) |
| `text_to_speech` | Generate speech audio from text via OpenAI TTS API |

## Tools Reference

### `transcribe_audio`

Transcribe speech from an audio file to text using Whisper API.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `file_base64` | string | no | Base64-encoded audio content |
| `file_path` | string | no | Path to audio file on disk |
| `telegram_file_id` | string | no | Telegram file_id to download and transcribe |
| `language` | string | no | Language hint (ISO 639-1: `vi`, `en`, `ja`, etc.) |

**Requires:** `OPENAI_API_KEY` environment variable

**Returns:** `text` (transcript), `language`, `duration`, `segments` (word-level timing)

### `get_audio_info`

Extract metadata from an audio file using mutagen.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `file_base64` | string | no | Base64-encoded audio content |
| `file_path` | string | no | Path to audio file on disk |
| `telegram_file_id` | string | no | Telegram file_id to download |

**Library:** `mutagen`

**Returns:** `format`, `duration_seconds`, `channels`, `sample_rate`, `bitrate`, `tags`, `file_size_bytes`

### `convert_audio`

Convert audio to a different format.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `output_format` | string | **yes** | Target: `mp3`, `wav`, `ogg`, `flac`, `aac`, `m4a` |
| `file_base64` | string | no | Base64-encoded audio |
| `file_path` | string | no | Path to audio file |
| `telegram_file_id` | string | no | Telegram file_id |
| `input_format` | string | no | Input format hint (auto-detected if omitted) |
| `bitrate` | string | no | Output bitrate: `128k`, `192k`, `320k` (default: `128k`) |
| `filename` | string | no | Output filename |

**Libraries:** `pydub` + `ffmpeg` on PATH

**Returns:** `filename`, `file_path`, `format`, `size_bytes`, `duration_seconds`, `file_base64`

### `text_to_speech`

Generate speech audio from text.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `text` | string | **yes** | Text to convert to speech |
| `voice` | string | no | Voice: `alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer` |
| `output_format` | string | no | Format: `mp3`, `opus`, `aac`, `flac`, `wav` (default: `mp3`) |
| `speed` | number | no | Playback speed 0.25–4.0 (default: 1.0) |
| `filename` | string | no | Output filename |

**Requires:** `OPENAI_API_KEY` environment variable

**Returns:** `filename`, `file_path`, `format`, `size_bytes`, `text_length`, `voice`, `file_base64`

### `download_telegram_audio`

Download an audio/voice file from Telegram by file_id.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `file_id` | string | **yes** | Telegram file_id from voice/audio message |
| `filename` | string | no | Save filename (auto-detected if omitted) |

**Requires:** `TELEGRAM_BOT_TOKEN` environment variable

**Returns:** `filename`, `file_path`, `size_bytes`, `file_base64`, `telegram_file_id`

## Telegram Voice Message Flow

When a user sends a voice message in Telegram:

```
1. Telegram webhook delivers update with message.voice.file_id
2. Gateway normalizes to IncomingMessage (text="[non-text message]", raw_payload=update)
3. Orchestrator classifies intent → routes to audio_processing agent
4. Agent detects voice in raw_payload → extracts file_id
5. Agent downloads OGG/OPUS file via Telegram Bot API (getFile)
6. Agent sends audio to Whisper API for transcription
7. Returns transcript + metadata to orchestrator
```

The agent auto-detects Telegram voice/audio messages from these `raw_payload` keys:
- `message.voice` — voice messages (OGG/OPUS)
- `message.audio` — audio files (MP3, etc.)
- `message.video_note` — video circles (extracts audio)
- `message.document` — document attachments (if audio MIME type)

## Architecture

```
input_data / context
  ├── telegram_file_id or raw_payload.voice  →  auto-transcribe
  ├── file_base64 / file_path (no text)      →  get_audio_info + transcribe
  └── text (+ optional file)                 →  LLM tool calling → tool dispatch
                                                 └── fallback: auto-transcribe or info
```

## Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | Required for downloading Telegram files |
| `OPENAI_API_KEY` | — | Required for Whisper transcription and TTS |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible API base URL |
| `VCLAW_WHISPER_MODEL` | `whisper-1` | Whisper model name |
| `VCLAW_TTS_MODEL` | `tts-1` | TTS model name |
| `VCLAW_TTS_VOICE` | `alloy` | Default TTS voice |
| `VCLAW_AUDIO_OUTPUT_DIR` | system temp dir | Output directory for audio files |

## Supported Audio Formats

| Format | Read/Info | Convert From | Convert To | Transcribe |
|---|---|---|---|---|
| OGG/OPUS | ✅ | ✅ | ✅ | ✅ |
| MP3 | ✅ | ✅ | ✅ | ✅ |
| WAV | ✅ | ✅ | ✅ | ✅ |
| FLAC | ✅ | ✅ | ✅ | ✅ |
| M4A | ✅ | ✅ | ✅ | ✅ |
| AAC | ✅ | ✅ | ✅ | ✅ |
| WebM | ✅ | ✅ | — | ✅ |

## Testing

```bash
python -m pytest tests/test_audio_processing_agent.py -v
```

Tests mock external APIs (Whisper, TTS, Telegram) and test metadata extraction + format conversion with real WAV data.

## Graceful Degradation

| Component | Missing | Behavior |
|---|---|---|
| `mutagen` | Not installed | `get_audio_info` returns error with install instructions |
| `pydub` | Not installed | `convert_audio` returns error with install instructions |
| `ffmpeg` | Not on PATH | `convert_audio` fails at export with helpful error |
| `OPENAI_API_KEY` | Not set | `transcribe_audio` and `text_to_speech` return error |
| `TELEGRAM_BOT_TOKEN` | Not set | `download_telegram_audio` and telegram_file_id ops return error |

The agent always registers successfully regardless of missing dependencies.
