"""Tests for image processing agent."""

from __future__ import annotations

import base64
import io
from pathlib import Path

import pytest
from PIL import Image

from vclaw.agents.builtin.image_processing.agent import ImageProcessingAgent
from vclaw.domain.models import AgentRequest


def _make_request(input_data: dict) -> AgentRequest:
    return AgentRequest(
        workflow_id="wf-test",
        subtask_id="st-test",
        agent_name="image_processing",
        input_data=input_data,
    )


def _create_test_image(width: int = 100, height: int = 80, color: str = "red") -> str:
    """Create a test image and return base64-encoded PNG."""
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img.close()
    return base64.b64encode(buf.getvalue()).decode("ascii")


# ---------------------------------------------------------------------------
# Manifest / setup
# ---------------------------------------------------------------------------


def test_image_agent_manifest() -> None:
    assert ImageProcessingAgent.manifest.name == "image_processing"
    cap_names = [c.name for c in ImageProcessingAgent.manifest.capabilities]
    assert "image_reading" in cap_names
    assert "image_analysis" in cap_names
    assert "image_manipulation" in cap_names
    assert "image_creation" in cap_names


@pytest.mark.asyncio
async def test_image_agent_setup_teardown() -> None:
    agent = ImageProcessingAgent()
    await agent.setup()
    assert await agent.health_check() is True
    await agent.teardown()


# ---------------------------------------------------------------------------
# get_image_info
# ---------------------------------------------------------------------------


def test_get_image_info_base64() -> None:
    agent = ImageProcessingAgent()
    b64 = _create_test_image(200, 150)

    result = agent._get_image_info(file_base64=b64)
    assert result["success"] is True
    assert result["data"]["width"] == 200
    assert result["data"]["height"] == 150
    assert result["data"]["mode"] == "RGB"


def test_get_image_info_file_path(tmp_path: Path) -> None:
    agent = ImageProcessingAgent()
    img_path = tmp_path / "test.png"
    img = Image.new("RGB", (50, 50), "blue")
    img.save(str(img_path))
    img.close()

    result = agent._get_image_info(file_path=str(img_path))
    assert result["success"] is True
    assert result["data"]["width"] == 50
    assert result["data"]["height"] == 50
    assert result["data"]["file_size_bytes"] > 0


# ---------------------------------------------------------------------------
# resize_image
# ---------------------------------------------------------------------------


def test_resize_image_keep_aspect() -> None:
    agent = ImageProcessingAgent()
    b64 = _create_test_image(400, 200)

    result = agent._resize_image(
        width=200,
        height=200,
        file_base64=b64,
        keep_aspect_ratio=True,
        output_format="png",
        filename="resized.png",
    )
    assert result["success"] is True
    assert result["data"]["width"] == 200
    assert result["data"]["height"] == 100

    Path(result["data"]["file_path"]).unlink(missing_ok=True)


def test_resize_image_exact() -> None:
    agent = ImageProcessingAgent()
    b64 = _create_test_image(400, 200)

    result = agent._resize_image(
        width=100,
        height=100,
        file_base64=b64,
        keep_aspect_ratio=False,
        filename="exact.png",
    )
    assert result["success"] is True
    assert result["data"]["width"] == 100
    assert result["data"]["height"] == 100

    Path(result["data"]["file_path"]).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# crop_image
# ---------------------------------------------------------------------------


def test_crop_image() -> None:
    agent = ImageProcessingAgent()
    b64 = _create_test_image(200, 200)

    result = agent._crop_image(
        left=10,
        top=10,
        right=110,
        bottom=110,
        file_base64=b64,
        filename="cropped.png",
    )
    assert result["success"] is True
    assert result["data"]["width"] == 100
    assert result["data"]["height"] == 100

    Path(result["data"]["file_path"]).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# rotate_image
# ---------------------------------------------------------------------------


def test_rotate_image() -> None:
    agent = ImageProcessingAgent()
    b64 = _create_test_image(100, 50)

    result = agent._rotate_image(
        degrees=90,
        file_base64=b64,
        expand=True,
        filename="rotated.png",
    )
    assert result["success"] is True
    assert result["data"]["width"] == 50
    assert result["data"]["height"] == 100

    Path(result["data"]["file_path"]).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# convert_format
# ---------------------------------------------------------------------------


def test_convert_png_to_jpeg() -> None:
    agent = ImageProcessingAgent()
    b64 = _create_test_image(100, 100)

    result = agent._convert_format(
        output_format="jpeg",
        file_base64=b64,
        quality=80,
        filename="converted.jpg",
    )
    assert result["success"] is True
    assert result["data"]["format"] == "jpeg"
    assert result["data"]["filename"] == "converted.jpg"

    Path(result["data"]["file_path"]).unlink(missing_ok=True)


def test_convert_to_webp() -> None:
    agent = ImageProcessingAgent()
    b64 = _create_test_image(100, 100)

    result = agent._convert_format(
        output_format="webp",
        file_base64=b64,
        filename="converted.webp",
    )
    assert result["success"] is True
    assert result["data"]["format"] == "webp"

    Path(result["data"]["file_path"]).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# create_image
# ---------------------------------------------------------------------------


def test_create_image_blank() -> None:
    agent = ImageProcessingAgent()

    result = agent._create_image(
        width=300,
        height=200,
        background_color="green",
        filename="blank.png",
    )
    assert result["success"] is True
    assert result["data"]["width"] == 300
    assert result["data"]["height"] == 200
    assert result["data"]["size_bytes"] > 0

    Path(result["data"]["file_path"]).unlink(missing_ok=True)


def test_create_image_with_text() -> None:
    agent = ImageProcessingAgent()

    result = agent._create_image(
        width=400,
        height=300,
        background_color="white",
        text="Hello Vietnam",
        text_color="red",
        font_size=24,
        filename="hello.png",
    )
    assert result["success"] is True
    assert result["data"]["width"] == 400
    assert result["data"]["file_base64"]

    Path(result["data"]["file_path"]).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Execute (no LLM)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_no_input() -> None:
    agent = ImageProcessingAgent()
    await agent.setup()

    req = _make_request({})
    resp = await agent.execute(req)
    assert resp.success is False
    assert "No input" in (resp.error or "")


@pytest.mark.asyncio
async def test_execute_direct_file_info() -> None:
    agent = ImageProcessingAgent()
    await agent.setup()

    b64 = _create_test_image(150, 100)
    req = _make_request({"file_base64": b64})
    resp = await agent.execute(req)
    assert resp.success is True
    assert "Image info" in resp.data.get("response_text", "")


@pytest.mark.asyncio
async def test_execute_file_path(tmp_path: Path) -> None:
    agent = ImageProcessingAgent()
    await agent.setup()

    img_path = tmp_path / "test.png"
    img = Image.new("RGB", (80, 60), "purple")
    img.save(str(img_path))
    img.close()

    req = _make_request({"file_path": str(img_path)})
    resp = await agent.execute(req)
    assert resp.success is True


# ---------------------------------------------------------------------------
# Format helpers
# ---------------------------------------------------------------------------


def test_format_get_image_info() -> None:
    agent = ImageProcessingAgent()
    result = agent._format_tool_result(
        "get_image_info",
        {
            "format": "PNG",
            "width": 640,
            "height": 480,
            "mode": "RGB",
            "file_size_bytes": 51200,
        },
    )
    assert "640" in result
    assert "480" in result
    assert "PNG" in result


def test_format_create_image() -> None:
    agent = ImageProcessingAgent()
    result = agent._format_tool_result(
        "create_image",
        {
            "filename": "out.png",
            "width": 800,
            "height": 600,
        },
    )
    assert "out.png" in result
    assert "800" in result


def test_format_analyze_image() -> None:
    agent = ImageProcessingAgent()
    result = agent._format_tool_result(
        "analyze_image",
        {
            "analysis": "A red square on white background",
        },
    )
    assert "red square" in result
