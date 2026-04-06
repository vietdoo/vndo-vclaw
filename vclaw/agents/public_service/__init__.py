"""
PublicServiceAgent: Government/public API querying for Vietnamese public services.
Supports: administrative procedures lookup, document status tracking, public announcements.
"""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any, ClassVar

import structlog

from vclaw.agents._base import AgentBase, AgentManifest, ToolDefinition
from vclaw.domain.models.base import (
    AgentCapability,
    AgentResult,
    SubTask,
)
from vclaw.infrastructure.llm import LLMMessage, LLMRouter, MockLLMProvider

logger = structlog.get_logger(__name__)

TOOLS = [
    ToolDefinition(
        name="lookup_procedure",
        description="Look up an administrative procedure by name or ID. Returns requirements, processing time, fees, and responsible agency.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Procedure name or keywords"},
                "procedure_id": {"type": "string", "description": "Specific procedure ID if known"},
                "province": {"type": "string", "description": "Province/city name in Vietnam"},
                "level": {"type": "string", "enum": ["central", "provincial", "district", "commune"]},
            },
            "required": ["query"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "procedures": {"type": "array"},
                "total": {"type": "integer"},
            },
        },
    ),
    ToolDefinition(
        name="track_document",
        description="Track the processing status of a submitted document or application by reference number.",
        input_schema={
            "type": "object",
            "properties": {
                "reference_number": {"type": "string"},
                "document_type": {"type": "string"},
                "submitter_id": {"type": "string"},
            },
            "required": ["reference_number"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "current_step": {"type": "string"},
                "estimated_completion": {"type": "string"},
                "history": {"type": "array"},
            },
        },
    ),
    ToolDefinition(
        name="get_announcements",
        description="Retrieve public service announcements, policy updates, or notices from government agencies.",
        input_schema={
            "type": "object",
            "properties": {
                "agency": {"type": "string"},
                "category": {"type": "string"},
                "limit": {"type": "integer", "default": 5},
                "since_date": {"type": "string", "format": "date"},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "announcements": {"type": "array"},
                "total": {"type": "integer"},
            },
        },
    ),
    ToolDefinition(
        name="calculate_fee",
        description="Calculate fees for a given administrative procedure.",
        input_schema={
            "type": "object",
            "properties": {
                "procedure_id": {"type": "string"},
                "quantity": {"type": "integer", "default": 1},
                "applicant_type": {"type": "string", "enum": ["individual", "organization"]},
            },
            "required": ["procedure_id"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "fee": {"type": "number"},
                "currency": {"type": "string"},
                "breakdown": {"type": "array"},
            },
        },
    ),
]

SYSTEM_PROMPT = """You are a Vietnamese public service assistant for the Vclaw platform.
Help citizens navigate government procedures and track their applications.

Use the available tools to:
- Look up administrative procedures (thủ tục hành chính)
- Track document/application status (tra cứu hồ sơ)
- Get public announcements (thông báo)
- Calculate procedure fees (lệ phí)

Always respond in Vietnamese. Be clear, accurate, and empathetic. 
Include relevant URLs, deadlines, and requirements when available.
If you cannot find specific information, suggest the appropriate government office to contact."""


class PublicServiceAgent(AgentBase):
    """
    Handles Vietnamese public service queries: procedure lookup, document tracking,
    announcements retrieval, and fee calculation.

    In production, integrates with:
    - Cổng dịch vụ công Quốc gia (dichvucong.gov.vn API)
    - Cơ sở dữ liệu thủ tục hành chính
    - Provincial government portals
    """

    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="Public Service Agent",
        agent_id="public-service-v1",
        version="1.0.0",
        description="Vietnamese public service assistant for procedures, document tracking, and government info",
        capabilities=[AgentCapability.PUBLIC_SERVICE],
        input_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "entities": {"type": "object"},
                "tenant": {"type": "object"},
            },
            "required": ["text"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "data": {"type": "object"},
                "action": {"type": "string"},
            },
        },
        tools=TOOLS,
        max_concurrent_tasks=20,
        timeout_seconds=25,
        priority=10,
        tags=["government", "public-service", "vietnam"],
        author="vclaw-core",
        requires_config=["PUBLIC_SERVICE_API_KEY"],
    )

    def __init__(self) -> None:
        super().__init__()
        self._llm: LLMRouter = LLMRouter(providers=[MockLLMProvider()])
        # Sample procedure database for demo
        self._procedures: dict[str, dict[str, Any]] = self._load_sample_procedures()

    def _load_sample_procedures(self) -> dict[str, dict[str, Any]]:
        """Sample Vietnamese administrative procedures for demo/testing."""
        return {
            "CMND-001": {
                "id": "CMND-001",
                "name": "Đổi Chứng minh nhân dân sang Căn cước công dân",
                "agency": "Công an cấp quận/huyện",
                "processing_days": 7,
                "fee": 0,
                "requirements": [
                    "Chứng minh nhân dân cũ",
                    "Hộ khẩu thường trú",
                    "01 ảnh 3x4 (chụp trong 6 tháng)",
                ],
                "steps": [
                    "Nộp hồ sơ tại cơ quan công an",
                    "Thu thập dữ liệu sinh trắc học",
                    "Thanh toán lệ phí (miễn phí)",
                    "Nhận kết quả",
                ],
                "online_url": "https://dichvucong.gov.vn/p/home/dvc-thu-tuc-hanh-chinh.html",
            },
            "DKKD-001": {
                "id": "DKKD-001",
                "name": "Đăng ký thành lập doanh nghiệp (Công ty TNHH)",
                "agency": "Phòng Đăng ký kinh doanh - Sở Kế hoạch và Đầu tư",
                "processing_days": 3,
                "fee": 50000,
                "requirements": [
                    "Giấy đề nghị đăng ký doanh nghiệp",
                    "Điều lệ công ty",
                    "Danh sách thành viên góp vốn",
                    "Bản sao CMND/CCCD các thành viên",
                ],
                "steps": [
                    "Chuẩn bị hồ sơ theo quy định",
                    "Nộp hồ sơ tại Phòng ĐKKD hoặc qua Cổng dịch vụ công",
                    "Thanh toán lệ phí",
                    "Nhận Giấy chứng nhận đăng ký doanh nghiệp",
                ],
                "online_url": "https://dangkykinhdoanh.gov.vn",
            },
        }

    async def execute(self, subtask: SubTask) -> AgentResult:
        text = subtask.input_data.get("text", "")
        entities = subtask.input_data.get("entities", {})
        tool_calls_made: list[dict[str, Any]] = []

        tools_spec = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_schema,
                },
            }
            for t in self.manifest.tools
        ]

        messages = [
            LLMMessage(role="system", content=SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content=f"User request: {text}\nExtracted entities: {entities}",
            ),
        ]

        response = await self._llm.complete(messages=messages, tools=tools_spec)
        result_output: dict[str, Any] = {}

        if response.tool_calls:
            for tc in response.tool_calls:
                tool_calls_made.append({"tool": tc.name, "args": tc.arguments})
                tool_result = await self.call_tool(tc.name, tc.arguments)
                result_output.update(tool_result)

            summary_messages = [
                *messages,
                LLMMessage(
                    role="user",
                    content=f"Tool results: {result_output}. Provide a clear, helpful Vietnamese response.",
                ),
            ]
            summary = await self._llm.complete(summary_messages)
            result_output["message"] = summary.content or self._format_result(result_output)
        else:
            result_output["message"] = response.content or "Đã xử lý yêu cầu của bạn."

        return AgentResult(
            subtask_id=subtask.subtask_id,
            agent_id=self.manifest.agent_id,
            success=True,
            output=result_output,
            tool_calls_made=tool_calls_made,
        )

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self._logger.debug("tool_call", tool=tool_name, args=arguments)

        if tool_name == "lookup_procedure":
            return await self._lookup_procedure(arguments)
        elif tool_name == "track_document":
            return await self._track_document(arguments)
        elif tool_name == "get_announcements":
            return await self._get_announcements(arguments)
        elif tool_name == "calculate_fee":
            return await self._calculate_fee(arguments)
        else:
            return {"error": f"Unknown tool: {tool_name}"}

    async def _lookup_procedure(self, args: dict[str, Any]) -> dict[str, Any]:
        query = args.get("query", "").lower()
        results = [
            p for p in self._procedures.values()
            if query in p["name"].lower() or query in p.get("agency", "").lower()
        ]
        if not results:
            results = list(self._procedures.values())[:3]

        return {
            "procedures": results,
            "total": len(results),
            "action": "lookup_procedure",
        }

    async def _track_document(self, args: dict[str, Any]) -> dict[str, Any]:
        ref = args.get("reference_number", "")
        # Deterministic mock status based on reference number hash
        status_options = ["Đang xử lý", "Chờ bổ sung hồ sơ", "Hoàn thành", "Đã trả kết quả"]
        idx = int(hashlib.md5(ref.encode()).hexdigest(), 16) % len(status_options)
        status = status_options[idx]
        return {
            "reference_number": ref,
            "status": status,
            "current_step": "Kiểm tra hồ sơ" if "xử lý" in status else "Hoàn tất",
            "estimated_completion": "3-5 ngày làm việc",
            "history": [
                {"date": "2024-01-01", "step": "Tiếp nhận hồ sơ", "status": "done"},
                {"date": "2024-01-02", "step": "Phân công xử lý", "status": "done"},
                {"date": "2024-01-03", "step": status, "status": "current"},
            ],
            "action": "track_document",
        }

    async def _get_announcements(self, args: dict[str, Any]) -> dict[str, Any]:
        limit = args.get("limit", 5)
        announcements = [
            {
                "id": f"ANN-{i:03d}",
                "title": f"Thông báo về dịch vụ công trực tuyến mức độ {i+3}",
                "agency": "Bộ Thông tin và Truyền thông",
                "date": datetime.now(UTC).strftime("%Y-%m-%d"),
                "summary": "Triển khai mở rộng dịch vụ công trực tuyến.",
                "url": f"https://mic.gov.vn/announcement/{i}",
            }
            for i in range(limit)
        ]
        return {
            "announcements": announcements,
            "total": len(announcements),
            "action": "get_announcements",
        }

    async def _calculate_fee(self, args: dict[str, Any]) -> dict[str, Any]:
        proc_id = args.get("procedure_id", "")
        quantity = args.get("quantity", 1)
        procedure = self._procedures.get(proc_id)
        if not procedure:
            return {"error": f"Procedure {proc_id} not found"}
        base_fee = procedure.get("fee", 0)
        total_fee = base_fee * quantity
        return {
            "procedure_id": proc_id,
            "fee": total_fee,
            "currency": "VND",
            "breakdown": [{"item": procedure["name"], "unit_fee": base_fee, "quantity": quantity}],
            "action": "calculate_fee",
        }

    @staticmethod
    def _format_result(output: dict[str, Any]) -> str:
        action = output.get("action", "")
        if action == "lookup_procedure":
            procs = output.get("procedures", [])
            if procs:
                p = procs[0]
                return (
                    f"📋 <b>{p['name']}</b>\n"
                    f"🏛 Cơ quan: {p['agency']}\n"
                    f"⏱ Thời gian: {p['processing_days']} ngày\n"
                    f"💰 Lệ phí: {p['fee']:,} VND\n"
                    f"🔗 {p.get('online_url', '')}"
                )
        if action == "track_document":
            return f"📄 Hồ sơ {output.get('reference_number')}: {output.get('status')}"
        return "Đã tra cứu thông tin dịch vụ công."


# Plugin discovery contract
agent_class = PublicServiceAgent
