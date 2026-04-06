"""Tests for DocumentProcessorAgent — run without LLM or file-system dependencies."""

from __future__ import annotations

import os
import tempfile
from typing import Any

import pytest

from vclaw.agents.builtin.document_processor.agent import (
    _DOCX_AVAILABLE,
    _FPDF_AVAILABLE,
    _OPENPYXL_AVAILABLE,
    _PYPDF_AVAILABLE,
    DocumentProcessorAgent,
)
from vclaw.domain.models import AgentRequest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(tool: str, args: dict[str, Any]) -> AgentRequest:
    return AgentRequest(
        workflow_id="wf-test",
        subtask_id="st-test",
        agent_name="document_processor",
        input_data={"tool": tool, "args": args},
    )


# ---------------------------------------------------------------------------
# Agent manifest and lifecycle
# ---------------------------------------------------------------------------


def test_manifest_fields() -> None:
    assert DocumentProcessorAgent.manifest.name == "document_processor"
    assert DocumentProcessorAgent.manifest.version == "0.1.0"
    cap_names = {c.name for c in DocumentProcessorAgent.manifest.capabilities}
    assert {"document_reading", "document_creation", "document_summarization"}.issubset(cap_names)
    tool_names = {t.name for t in DocumentProcessorAgent.manifest.tools}
    assert {"read_pdf", "read_word", "read_excel", "create_pdf", "create_word", "create_excel", "summarize_document"}.issubset(tool_names)


@pytest.mark.asyncio
async def test_setup_teardown() -> None:
    agent = DocumentProcessorAgent()
    await agent.setup()
    assert agent._semaphore is not None
    await agent.teardown()


# ---------------------------------------------------------------------------
# Missing-library error responses (always work regardless of install state)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_pdf_missing_file() -> None:
    """Should return success=False with a clear error when file is absent."""
    agent = DocumentProcessorAgent()
    await agent.setup()
    resp = await agent.run(_make_request("read_pdf", {"file_path": "/nonexistent/file.pdf"}))
    assert resp.success is False
    assert "not found" in (resp.error or "").lower() or "not installed" in (resp.error or "").lower()


@pytest.mark.asyncio
async def test_read_word_missing_file() -> None:
    agent = DocumentProcessorAgent()
    await agent.setup()
    resp = await agent.run(_make_request("read_word", {"file_path": "/nonexistent/file.docx"}))
    assert resp.success is False


@pytest.mark.asyncio
async def test_read_excel_missing_file() -> None:
    agent = DocumentProcessorAgent()
    await agent.setup()
    resp = await agent.run(_make_request("read_excel", {"file_path": "/nonexistent/file.xlsx"}))
    assert resp.success is False


@pytest.mark.asyncio
async def test_unknown_tool() -> None:
    agent = DocumentProcessorAgent()
    await agent.setup()
    resp = await agent.run(_make_request("unknown_tool", {}))
    assert resp.success is False


@pytest.mark.asyncio
async def test_empty_input_returns_error() -> None:
    agent = DocumentProcessorAgent()
    await agent.setup()
    req = AgentRequest(
        workflow_id="wf-1",
        subtask_id="st-1",
        agent_name="document_processor",
        input_data={},
    )
    resp = await agent.run(req)
    assert resp.success is False
    assert resp.error is not None


@pytest.mark.asyncio
async def test_summarize_unsupported_extension() -> None:
    agent = DocumentProcessorAgent()
    await agent.setup()
    resp = await agent.run(
        _make_request("summarize_document", {"file_path": "/tmp/file.mp3"})
    )
    assert resp.success is False
    assert "unsupported" in (resp.error or "").lower()


# ---------------------------------------------------------------------------
# PDF creation + reading (requires fpdf2 + pypdf)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _FPDF_AVAILABLE, reason="fpdf2 not installed")
@pytest.mark.asyncio
async def test_create_pdf_produces_file() -> None:
    agent = DocumentProcessorAgent()
    await agent.setup()

    with tempfile.TemporaryDirectory() as tmpdir:
        resp = await agent.run(
            _make_request(
                "create_pdf",
                {
                    "filename": "test.pdf",
                    "title": "Test Document",
                    "content": "Hello from vclaw.\nThis is a test PDF.",
                    "output_dir": tmpdir,
                },
            )
        )
        assert resp.success, resp.error
        out_path = resp.data.get("file_path", "")
        assert os.path.isfile(out_path)
        assert resp.data["size_bytes"] > 0


@pytest.mark.skipif(not (_FPDF_AVAILABLE and _PYPDF_AVAILABLE), reason="fpdf2 or pypdf not installed")
@pytest.mark.asyncio
async def test_create_and_read_pdf_roundtrip() -> None:
    agent = DocumentProcessorAgent()
    await agent.setup()

    with tempfile.TemporaryDirectory() as tmpdir:
        content = "Roundtrip content. Line two here."
        create_resp = await agent.run(
            _make_request(
                "create_pdf",
                {"filename": "rt.pdf", "content": content, "output_dir": tmpdir},
            )
        )
        assert create_resp.success, create_resp.error

        read_resp = await agent.run(
            _make_request("read_pdf", {"file_path": create_resp.data["file_path"]})
        )
        assert read_resp.success, read_resp.error
        assert read_resp.data["total_pages"] >= 1
        assert isinstance(read_resp.data["text"], str)


# ---------------------------------------------------------------------------
# Word creation + reading (requires python-docx)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _DOCX_AVAILABLE, reason="python-docx not installed")
@pytest.mark.asyncio
async def test_create_word_produces_file() -> None:
    agent = DocumentProcessorAgent()
    await agent.setup()

    with tempfile.TemporaryDirectory() as tmpdir:
        resp = await agent.run(
            _make_request(
                "create_word",
                {
                    "filename": "test.docx",
                    "title": "My Report",
                    "sections": [
                        {"heading": "Introduction", "body": "This is the intro."},
                        {"heading": "Kết luận", "body": "Đây là kết luận."},
                    ],
                    "output_dir": tmpdir,
                },
            )
        )
        assert resp.success, resp.error
        assert os.path.isfile(resp.data["file_path"])
        assert resp.data["size_bytes"] > 0


@pytest.mark.skipif(not _DOCX_AVAILABLE, reason="python-docx not installed")
@pytest.mark.asyncio
async def test_create_and_read_word_roundtrip() -> None:
    agent = DocumentProcessorAgent()
    await agent.setup()

    with tempfile.TemporaryDirectory() as tmpdir:
        body_text = "Section body content for testing."
        create_resp = await agent.run(
            _make_request(
                "create_word",
                {
                    "filename": "rt.docx",
                    "title": "Roundtrip",
                    "sections": [{"heading": "S1", "body": body_text}],
                    "output_dir": tmpdir,
                },
            )
        )
        assert create_resp.success, create_resp.error

        read_resp = await agent.run(
            _make_request("read_word", {"file_path": create_resp.data["file_path"]})
        )
        assert read_resp.success, read_resp.error
        assert body_text in read_resp.data["text"]
        assert read_resp.data["paragraph_count"] >= 1


# ---------------------------------------------------------------------------
# Excel creation + reading (requires openpyxl)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _OPENPYXL_AVAILABLE, reason="openpyxl not installed")
@pytest.mark.asyncio
async def test_create_excel_produces_file() -> None:
    agent = DocumentProcessorAgent()
    await agent.setup()

    with tempfile.TemporaryDirectory() as tmpdir:
        resp = await agent.run(
            _make_request(
                "create_excel",
                {
                    "filename": "data.xlsx",
                    "headers": ["Name", "Score"],
                    "rows": [["Alice", 95], ["Bob", 88]],
                    "sheet_name": "Results",
                    "output_dir": tmpdir,
                },
            )
        )
        assert resp.success, resp.error
        assert os.path.isfile(resp.data["file_path"])
        assert resp.data["row_count"] == 2
        assert resp.data["size_bytes"] > 0


@pytest.mark.skipif(not _OPENPYXL_AVAILABLE, reason="openpyxl not installed")
@pytest.mark.asyncio
async def test_create_and_read_excel_roundtrip() -> None:
    agent = DocumentProcessorAgent()
    await agent.setup()

    with tempfile.TemporaryDirectory() as tmpdir:
        headers = ["Product", "Quantity"]
        rows = [["Widget A", 10], ["Widget B", 20]]
        create_resp = await agent.run(
            _make_request(
                "create_excel",
                {
                    "filename": "rt.xlsx",
                    "headers": headers,
                    "rows": rows,
                    "output_dir": tmpdir,
                },
            )
        )
        assert create_resp.success, create_resp.error

        read_resp = await agent.run(
            _make_request("read_excel", {"file_path": create_resp.data["file_path"]})
        )
        assert read_resp.success, read_resp.error
        # headers row + 2 data rows
        assert read_resp.data["total_rows"] >= 2


@pytest.mark.skipif(not _OPENPYXL_AVAILABLE, reason="openpyxl not installed")
@pytest.mark.asyncio
async def test_read_excel_specific_sheet() -> None:
    agent = DocumentProcessorAgent()
    await agent.setup()

    with tempfile.TemporaryDirectory() as tmpdir:
        create_resp = await agent.run(
            _make_request(
                "create_excel",
                {
                    "filename": "sheets.xlsx",
                    "headers": ["Col"],
                    "rows": [["val1"]],
                    "sheet_name": "MySheet",
                    "output_dir": tmpdir,
                },
            )
        )
        assert create_resp.success

        read_resp = await agent.run(
            _make_request(
                "read_excel",
                {
                    "file_path": create_resp.data["file_path"],
                    "sheet_name": "MySheet",
                },
            )
        )
        assert read_resp.success
        assert "MySheet" in read_resp.data["sheets_read"]


# ---------------------------------------------------------------------------
# Summarize falls back gracefully without LLM
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _FPDF_AVAILABLE, reason="fpdf2 not installed")
@pytest.mark.asyncio
async def test_summarize_pdf_no_llm_fallback() -> None:
    """Without an LLM router, summarize returns the raw text snippet."""
    agent = DocumentProcessorAgent()  # no llm_router
    await agent.setup()

    with tempfile.TemporaryDirectory() as tmpdir:
        create_resp = await agent.run(
            _make_request(
                "create_pdf",
                {"filename": "s.pdf", "content": "Summary test content.", "output_dir": tmpdir},
            )
        )
        assert create_resp.success

        sum_resp = await agent.run(
            _make_request("summarize_document", {"file_path": create_resp.data["file_path"]})
        )
        assert sum_resp.success is True
        assert "LLM unavailable" in sum_resp.data.get("summary", "")
