"""Tests for document processing agent (PDF, DOCX, XLSX)."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from vclaw.agents.builtin.document_processing.agent import DocumentProcessingAgent
from vclaw.domain.models import AgentRequest


def _make_request(input_data: dict) -> AgentRequest:
    return AgentRequest(
        workflow_id="wf-test",
        subtask_id="st-test",
        agent_name="document_processing",
        input_data=input_data,
    )


# ---------------------------------------------------------------------------
# Manifest / setup
# ---------------------------------------------------------------------------


def test_document_agent_manifest() -> None:
    assert DocumentProcessingAgent.manifest.name == "document_processing"
    cap_names = [c.name for c in DocumentProcessingAgent.manifest.capabilities]
    assert "document_reading" in cap_names
    assert "document_creation" in cap_names
    assert "document_info" in cap_names


@pytest.mark.asyncio
async def test_document_agent_setup_teardown() -> None:
    agent = DocumentProcessingAgent()
    await agent.setup()
    assert await agent.health_check() is True
    await agent.teardown()


# ---------------------------------------------------------------------------
# PDF operations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_pdf() -> None:
    agent = DocumentProcessingAgent()
    await agent.setup()

    result = agent._create_pdf(
        content="Hello World\nThis is a test PDF.",
        title="Test Document",
        filename="test_output.pdf",
    )
    assert result["success"] is True
    assert result["data"]["filename"] == "test_output.pdf"
    assert result["data"]["size_bytes"] > 0
    assert result["data"]["file_base64"]

    file_path = result["data"]["file_path"]
    assert Path(file_path).exists()
    Path(file_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_read_pdf_from_created() -> None:
    agent = DocumentProcessingAgent()
    await agent.setup()

    create_result = agent._create_pdf(
        content="Test content for reading.",
        title="Read Test",
        filename="test_read.pdf",
    )
    assert create_result["success"] is True

    read_result = agent._read_pdf(file_base64=create_result["data"]["file_base64"])
    assert read_result["success"] is True
    assert read_result["data"]["page_count"] >= 1
    assert "Test content" in read_result["data"]["text"]

    Path(create_result["data"]["file_path"]).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_read_pdf_specific_pages() -> None:
    agent = DocumentProcessingAgent()
    await agent.setup()

    create_result = agent._create_pdf(content="Page content", filename="pages.pdf")
    assert create_result["success"]

    read_result = agent._read_pdf(
        file_base64=create_result["data"]["file_base64"],
        page_numbers=[0],
    )
    assert read_result["success"]
    assert read_result["data"]["pages_read"] == 1

    Path(create_result["data"]["file_path"]).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# DOCX operations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_docx() -> None:
    agent = DocumentProcessingAgent()
    await agent.setup()

    result = agent._create_docx(
        content="First paragraph\nSecond paragraph",
        title="Test DOCX",
        filename="test_output.docx",
    )
    assert result["success"] is True
    assert result["data"]["filename"] == "test_output.docx"
    assert result["data"]["size_bytes"] > 0

    Path(result["data"]["file_path"]).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_create_docx_with_sections() -> None:
    agent = DocumentProcessingAgent()
    await agent.setup()

    result = agent._create_docx(
        content="",
        title="Sections Test",
        sections=[
            {"heading": "Introduction", "body": "This is the intro."},
            {"heading": "Details", "body": "More details here."},
        ],
        filename="sections.docx",
    )
    assert result["success"] is True

    Path(result["data"]["file_path"]).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_read_docx_from_created() -> None:
    agent = DocumentProcessingAgent()
    await agent.setup()

    create_result = agent._create_docx(
        content="Paragraph one\nParagraph two",
        title="Read DOCX",
        filename="read_test.docx",
    )
    assert create_result["success"]

    read_result = agent._read_docx(file_base64=create_result["data"]["file_base64"])
    assert read_result["success"]
    assert read_result["data"]["paragraph_count"] >= 2
    assert "Paragraph one" in read_result["data"]["text"]

    Path(create_result["data"]["file_path"]).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# XLSX operations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_xlsx() -> None:
    agent = DocumentProcessingAgent()
    await agent.setup()

    result = agent._create_xlsx(
        headers=["Name", "Age", "City"],
        rows=[
            ["Alice", 30, "Hanoi"],
            ["Bob", 25, "HCMC"],
        ],
        title="People",
        filename="test_output.xlsx",
    )
    assert result["success"] is True
    assert result["data"]["filename"] == "test_output.xlsx"
    assert result["data"]["size_bytes"] > 0

    Path(result["data"]["file_path"]).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_read_xlsx_from_created() -> None:
    agent = DocumentProcessingAgent()
    await agent.setup()

    create_result = agent._create_xlsx(
        headers=["Product", "Price"],
        rows=[["Widget", "10.00"], ["Gadget", "20.00"]],
        filename="read_test.xlsx",
    )
    assert create_result["success"]

    read_result = agent._read_xlsx(file_base64=create_result["data"]["file_base64"])
    assert read_result["success"]
    assert read_result["data"]["row_count"] == 2
    assert "Product" in read_result["data"]["headers"]
    assert "Price" in read_result["data"]["headers"]

    Path(create_result["data"]["file_path"]).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Document info
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_document_info_pdf() -> None:
    agent = DocumentProcessingAgent()
    await agent.setup()

    create_result = agent._create_pdf(content="Info test", filename="info.pdf")
    assert create_result["success"]

    info = agent._get_document_info(
        file_type="pdf",
        file_base64=create_result["data"]["file_base64"],
    )
    assert info["success"]
    assert info["data"]["page_count"] >= 1
    assert info["data"]["file_type"] == "pdf"

    Path(create_result["data"]["file_path"]).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_get_document_info_docx() -> None:
    agent = DocumentProcessingAgent()
    await agent.setup()

    create_result = agent._create_docx(content="Info test", filename="info.docx")
    assert create_result["success"]

    info = agent._get_document_info(
        file_type="docx",
        file_base64=create_result["data"]["file_base64"],
    )
    assert info["success"]
    assert info["data"]["file_type"] == "docx"

    Path(create_result["data"]["file_path"]).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_get_document_info_xlsx() -> None:
    agent = DocumentProcessingAgent()
    await agent.setup()

    create_result = agent._create_xlsx(headers=["A", "B"], rows=[["1", "2"]], filename="info.xlsx")
    assert create_result["success"]

    info = agent._get_document_info(
        file_type="xlsx",
        file_base64=create_result["data"]["file_base64"],
    )
    assert info["success"]
    assert info["data"]["file_type"] == "xlsx"
    assert info["data"]["sheet_count"] >= 1

    Path(create_result["data"]["file_path"]).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# File type detection
# ---------------------------------------------------------------------------


def test_detect_file_type() -> None:
    assert DocumentProcessingAgent._detect_file_type("report.pdf") == "pdf"
    assert DocumentProcessingAgent._detect_file_type("report.docx") == "docx"
    assert DocumentProcessingAgent._detect_file_type("report.doc") == "docx"
    assert DocumentProcessingAgent._detect_file_type("report.xlsx") == "xlsx"
    assert DocumentProcessingAgent._detect_file_type("report.xls") == "xlsx"
    assert DocumentProcessingAgent._detect_file_type("") == ""


# ---------------------------------------------------------------------------
# Execute (no LLM) — fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_no_input() -> None:
    agent = DocumentProcessingAgent()
    await agent.setup()

    req = _make_request({})
    resp = await agent.execute(req)
    assert resp.success is False
    assert "No input" in (resp.error or "")


@pytest.mark.asyncio
async def test_execute_with_file_direct() -> None:
    agent = DocumentProcessingAgent()
    await agent.setup()

    create_result = agent._create_pdf(content="Direct test", filename="direct.pdf")
    assert create_result["success"]

    req = _make_request(
        {
            "file_base64": create_result["data"]["file_base64"],
            "file_type": "pdf",
        }
    )
    resp = await agent.execute(req)
    assert resp.success is True
    assert "PDF" in resp.data.get("response_text", "")

    Path(create_result["data"]["file_path"]).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_execute_with_file_path() -> None:
    agent = DocumentProcessingAgent()
    await agent.setup()

    create_result = agent._create_docx(content="Path test", filename="pathtest.docx")
    assert create_result["success"]
    file_path = create_result["data"]["file_path"]

    req = _make_request({"file_path": file_path})
    resp = await agent.execute(req)
    assert resp.success is True

    Path(file_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_execute_unsupported_file_type() -> None:
    agent = DocumentProcessingAgent()
    await agent.setup()

    req = _make_request(
        {
            "file_base64": base64.b64encode(b"fake").decode(),
            "file_type": "txt",
        }
    )
    resp = await agent.execute(req)
    assert resp.success is False
    assert "Unsupported" in (resp.error or "")


# ---------------------------------------------------------------------------
# Tool result formatting
# ---------------------------------------------------------------------------


def test_format_tool_result_read_pdf() -> None:
    agent = DocumentProcessingAgent()
    result = agent._format_tool_result(
        "read_pdf",
        {
            "text": "Hello world",
            "page_count": 3,
        },
    )
    assert "PDF" in result
    assert "pages: 3" in result


def test_format_tool_result_create_xlsx() -> None:
    agent = DocumentProcessingAgent()
    result = agent._format_tool_result(
        "create_xlsx",
        {
            "filename": "data.xlsx",
            "size_bytes": 12345,
        },
    )
    assert "data.xlsx" in result
    assert "12,345" in result
