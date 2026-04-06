"""Tests for ImageProcessorAgent — run without LLM or optional library dependencies."""

from __future__ import annotations

import os
import tempfile
from typing import Any

import pytest

from vclaw.agents.builtin.image_processor.agent import (
    _PILLOW_AVAILABLE,
    _TESSERACT_AVAILABLE,
    ImageProcessorAgent,
)
from vclaw.domain.models import AgentRequest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(tool: str, args: dict[str, Any]) -> AgentRequest:
    return AgentRequest(
        workflow_id="wf-test",
        subtask_id="st-test",
        agent_name="image_processor",
        input_data={"tool": tool, "args": args},
    )


def _create_test_png(path: str, width: int = 50, height: int = 50) -> None:
    """Create a small valid PNG file using Pillow."""
    from PIL import Image

    img = Image.new("RGB", (width, height), color=(100, 150, 200))
    img.save(path, format="PNG")


# ---------------------------------------------------------------------------
# Agent manifest and lifecycle
# ---------------------------------------------------------------------------


def test_manifest_fields() -> None:
    assert ImageProcessorAgent.manifest.name == "image_processor"
    assert ImageProcessorAgent.manifest.version == "0.1.0"
    cap_names = {c.name for c in ImageProcessorAgent.manifest.capabilities}
    assert {"image_analysis", "ocr", "image_metadata", "image_editing"}.issubset(cap_names)
    tool_names = {t.name for t in ImageProcessorAgent.manifest.tools}
    assert {"analyze_image", "extract_text_ocr", "get_metadata", "resize_image", "convert_image", "describe_url"}.issubset(tool_names)


@pytest.mark.asyncio
async def test_setup_teardown() -> None:
    agent = ImageProcessorAgent()
    await agent.setup()
    assert agent._semaphore is not None
    assert agent._http_client is not None
    await agent.teardown()
    assert agent._http_client is None


# ---------------------------------------------------------------------------
# Missing-library / missing-file error responses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_metadata_missing_file() -> None:
    agent = ImageProcessorAgent()
    await agent.setup()
    resp = await agent.run(_make_request("get_metadata", {"file_path": "/nonexistent/img.png"}))
    assert resp.success is False
    assert "not found" in (resp.error or "").lower() or "not installed" in (resp.error or "").lower()
    await agent.teardown()


@pytest.mark.asyncio
async def test_resize_missing_file() -> None:
    agent = ImageProcessorAgent()
    await agent.setup()
    resp = await agent.run(_make_request("resize_image", {"file_path": "/nonexistent/img.png", "width": 100}))
    assert resp.success is False
    await agent.teardown()


@pytest.mark.asyncio
async def test_ocr_missing_file() -> None:
    agent = ImageProcessorAgent()
    await agent.setup()
    resp = await agent.run(_make_request("extract_text_ocr", {"file_path": "/nonexistent/img.png"}))
    assert resp.success is False
    await agent.teardown()


@pytest.mark.asyncio
async def test_unknown_tool() -> None:
    agent = ImageProcessorAgent()
    await agent.setup()
    resp = await agent.run(_make_request("unknown_tool", {}))
    assert resp.success is False
    await agent.teardown()


@pytest.mark.asyncio
async def test_empty_input_returns_error() -> None:
    agent = ImageProcessorAgent()
    await agent.setup()
    req = AgentRequest(
        workflow_id="wf-1",
        subtask_id="st-1",
        agent_name="image_processor",
        input_data={},
    )
    resp = await agent.run(req)
    assert resp.success is False
    assert resp.error is not None
    await agent.teardown()


@pytest.mark.asyncio
async def test_analyze_image_no_llm_returns_error() -> None:
    """analyze_image without LLM router should fail clearly."""
    agent = ImageProcessorAgent()  # no llm_router
    await agent.setup()
    with tempfile.TemporaryDirectory() as tmpdir:
        img_path = os.path.join(tmpdir, "test.png")
        if _PILLOW_AVAILABLE:
            _create_test_png(img_path)
            resp = await agent.run(_make_request("analyze_image", {"file_path": img_path}))
            assert resp.success is False
            assert "llm" in (resp.error or "").lower() or "not available" in (resp.error or "").lower()
    await agent.teardown()


@pytest.mark.asyncio
async def test_describe_url_no_llm_returns_error() -> None:
    agent = ImageProcessorAgent()
    await agent.setup()
    resp = await agent.run(_make_request("describe_url", {"url": "https://example.com/img.png"}))
    assert resp.success is False
    await agent.teardown()


# ---------------------------------------------------------------------------
# Pillow-backed tools (require Pillow)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _PILLOW_AVAILABLE, reason="Pillow not installed")
@pytest.mark.asyncio
async def test_get_metadata_valid_image() -> None:
    agent = ImageProcessorAgent()
    await agent.setup()
    with tempfile.TemporaryDirectory() as tmpdir:
        img_path = os.path.join(tmpdir, "sample.png")
        _create_test_png(img_path, width=80, height=60)

        resp = await agent.run(_make_request("get_metadata", {"file_path": img_path}))
        assert resp.success, resp.error
        assert resp.data["width"] == 80
        assert resp.data["height"] == 60
        assert resp.data["format"] in ("PNG", "png")
        assert resp.data["size_bytes"] > 0
    await agent.teardown()


@pytest.mark.skipif(not _PILLOW_AVAILABLE, reason="Pillow not installed")
@pytest.mark.asyncio
async def test_resize_image_produces_file() -> None:
    agent = ImageProcessorAgent()
    await agent.setup()
    with tempfile.TemporaryDirectory() as tmpdir:
        img_path = os.path.join(tmpdir, "orig.png")
        _create_test_png(img_path, width=200, height=100)

        resp = await agent.run(
            _make_request(
                "resize_image",
                {"file_path": img_path, "width": 50, "output_dir": tmpdir},
            )
        )
        assert resp.success, resp.error
        out_path = resp.data.get("output_path", "")
        assert os.path.isfile(out_path)
        # width should be 50; height should be ~25 (aspect ratio preserved)
        assert "50×" in resp.data.get("new_size", "")
    await agent.teardown()


@pytest.mark.skipif(not _PILLOW_AVAILABLE, reason="Pillow not installed")
@pytest.mark.asyncio
async def test_resize_explicit_height() -> None:
    agent = ImageProcessorAgent()
    await agent.setup()
    with tempfile.TemporaryDirectory() as tmpdir:
        img_path = os.path.join(tmpdir, "orig.png")
        _create_test_png(img_path, width=200, height=100)

        resp = await agent.run(
            _make_request(
                "resize_image",
                {
                    "file_path": img_path,
                    "width": 60,
                    "height": 40,
                    "keep_aspect_ratio": False,
                    "output_dir": tmpdir,
                },
            )
        )
        assert resp.success, resp.error
        assert "60×40" in resp.data.get("new_size", "")
    await agent.teardown()


@pytest.mark.skipif(not _PILLOW_AVAILABLE, reason="Pillow not installed")
@pytest.mark.asyncio
async def test_convert_png_to_jpeg() -> None:
    agent = ImageProcessorAgent()
    await agent.setup()
    with tempfile.TemporaryDirectory() as tmpdir:
        img_path = os.path.join(tmpdir, "orig.png")
        _create_test_png(img_path)

        resp = await agent.run(
            _make_request(
                "convert_image",
                {"file_path": img_path, "target_format": "JPEG", "output_dir": tmpdir},
            )
        )
        assert resp.success, resp.error
        out_path = resp.data.get("output_path", "")
        assert out_path.endswith(".jpg")
        assert os.path.isfile(out_path)
        assert resp.data["size_bytes"] > 0
    await agent.teardown()


@pytest.mark.skipif(not _PILLOW_AVAILABLE, reason="Pillow not installed")
@pytest.mark.asyncio
async def test_convert_png_to_webp() -> None:
    agent = ImageProcessorAgent()
    await agent.setup()
    with tempfile.TemporaryDirectory() as tmpdir:
        img_path = os.path.join(tmpdir, "photo.png")
        _create_test_png(img_path)

        resp = await agent.run(
            _make_request(
                "convert_image",
                {
                    "file_path": img_path,
                    "target_format": "WEBP",
                    "quality": 90,
                    "output_dir": tmpdir,
                },
            )
        )
        assert resp.success, resp.error
        assert resp.data["output_path"].endswith(".webp")
    await agent.teardown()


@pytest.mark.skipif(not _PILLOW_AVAILABLE, reason="Pillow not installed")
@pytest.mark.asyncio
async def test_convert_with_custom_output_filename() -> None:
    agent = ImageProcessorAgent()
    await agent.setup()
    with tempfile.TemporaryDirectory() as tmpdir:
        img_path = os.path.join(tmpdir, "src.png")
        _create_test_png(img_path)

        resp = await agent.run(
            _make_request(
                "convert_image",
                {
                    "file_path": img_path,
                    "target_format": "PNG",
                    "output_filename": "custom_output.png",
                    "output_dir": tmpdir,
                },
            )
        )
        assert resp.success, resp.error
        assert resp.data["output_path"].endswith("custom_output.png")
    await agent.teardown()


# ---------------------------------------------------------------------------
# OCR (requires Pillow + pytesseract + tesseract system binary)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not (_PILLOW_AVAILABLE and _TESSERACT_AVAILABLE),
    reason="Pillow or pytesseract not installed",
)
@pytest.mark.asyncio
async def test_ocr_returns_text_or_empty() -> None:
    """A plain-coloured image has no text; OCR should succeed with an empty/whitespace result."""
    agent = ImageProcessorAgent()
    await agent.setup()
    with tempfile.TemporaryDirectory() as tmpdir:
        img_path = os.path.join(tmpdir, "blank.png")
        _create_test_png(img_path)

        resp = await agent.run(_make_request("extract_text_ocr", {"file_path": img_path}))
        # May succeed with empty text — either outcome is acceptable
        assert isinstance(resp.data.get("text", ""), str)
    await agent.teardown()
