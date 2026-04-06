"""Public service agent for government API querying and citizen service tracking."""

from __future__ import annotations

import json
from datetime import UTC, datetime
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


class PublicServiceDirectory:
    """Simulated public service directory (replace with real API integration)."""

    SERVICES: dict[str, dict[str, Any]] = {
        "cccd": {
            "name": "Căn cước công dân (CCCD)",
            "name_en": "National ID Card",
            "agency": "Công an",
            "processing_days": 7,
            "required_docs": ["Hộ khẩu", "Ảnh 4x6", "Đơn đề nghị"],
            "fee": "Free",
            "status_url": "https://dichvucong.gov.vn",
        },
        "passport": {
            "name": "Hộ chiếu",
            "name_en": "Passport",
            "agency": "Cục Quản lý xuất nhập cảnh",
            "processing_days": 8,
            "required_docs": ["CCCD", "Ảnh 4x6", "Đơn đề nghị", "Lệ phí"],
            "fee": "200,000 VND",
            "status_url": "https://xuatnhapcanh.gov.vn",
        },
        "business_license": {
            "name": "Giấy phép kinh doanh",
            "name_en": "Business License",
            "agency": "Sở Kế hoạch và Đầu tư",
            "processing_days": 3,
            "required_docs": ["CCCD", "Điều lệ công ty", "Danh sách thành viên"],
            "fee": "Varies",
            "status_url": "https://dangkykinhdoanh.gov.vn",
        },
        "land_certificate": {
            "name": "Sổ đỏ (Giấy chứng nhận QSDĐ)",
            "name_en": "Land Use Right Certificate",
            "agency": "Sở Tài nguyên và Môi trường",
            "processing_days": 30,
            "required_docs": ["CCCD", "Hợp đồng mua bán", "Bản đồ đất"],
            "fee": "Varies by area",
            "status_url": "https://dichvucong.gov.vn",
        },
    }

    _applications: dict[str, dict[str, Any]] = {}
    _counter: int = 0

    @classmethod
    def lookup_service(cls, service_key: str) -> dict[str, Any] | None:
        key = service_key.lower().replace(" ", "_")
        return cls.SERVICES.get(key)

    @classmethod
    def list_services(cls) -> list[dict[str, Any]]:
        return [{"key": k, **v} for k, v in cls.SERVICES.items()]

    @classmethod
    def submit_application(
        cls,
        service_key: str,
        citizen_id: str,
        notes: str = "",
    ) -> dict[str, Any]:
        cls._counter += 1
        app_id = f"APP-{cls._counter:06d}"
        days = cls.SERVICES.get(service_key, {}).get("processing_days", "N/A")
        application = {
            "application_id": app_id,
            "service": service_key,
            "citizen_id": citizen_id,
            "status": "submitted",
            "notes": notes,
            "submitted_at": datetime.now(UTC).isoformat(),
            "estimated_completion": f"{days} days",
        }
        cls._applications[app_id] = application
        return application

    @classmethod
    def check_status(cls, application_id: str) -> dict[str, Any] | None:
        return cls._applications.get(application_id)


class PublicServiceAgent(AgentBase):
    """Agent for querying Vietnamese public/government services.

    Provides information about required documents, processing times,
    fees, and application status tracking.
    """

    manifest: ClassVar[AgentManifest] = AgentManifest(
        name="public_service",
        version="0.1.0",
        description=(
            "Queries Vietnamese public services: required documents, "
            "processing times, fees, and application status."
        ),
        capabilities=[
            AgentCapability(
                name="public_service",
                description=(
                    "Look up government services, required documents, "
                    "fees, and processing times"
                ),
            ),
            AgentCapability(
                name="application_tracking",
                description="Submit and track public service applications",
            ),
        ],
        tools=[
            ToolDefinition(
                name="lookup_service",
                description=(
                    "Look up details about a public service "
                    "(documents needed, fees, processing time)"
                ),
                parameters={
                    "service_key": {
                        "type": "string",
                        "description": (
                            "Service identifier: cccd, passport, "
                            "business_license, land_certificate"
                        ),
                    },
                },
                required_params=["service_key"],
            ),
            ToolDefinition(
                name="list_services",
                description="List all available public services",
                parameters={},
                required_params=[],
            ),
            ToolDefinition(
                name="submit_application",
                description="Submit a new application for a public service",
                parameters={
                    "service_key": {"type": "string", "description": "Service identifier"},
                    "citizen_id": {"type": "string", "description": "Citizen ID number"},
                    "notes": {"type": "string", "description": "Additional notes"},
                },
                required_params=["service_key", "citizen_id"],
            ),
            ToolDefinition(
                name="check_status",
                description="Check the status of an existing application",
                parameters={
                    "application_id": {
                        "type": "string",
                        "description": "Application ID (e.g. APP-000001)",
                    },
                },
                required_params=["application_id"],
            ),
        ],
        retry_policy=RetryPolicy(max_retries=2, base_delay_seconds=1.0),
        tags=["government", "public_service", "vietnam"],
    )

    async def execute(self, request: AgentRequest) -> AgentResponse:
        text = request.input_data.get("text", "")
        if not text:
            return AgentResponse(
                workflow_id=request.workflow_id,
                subtask_id=request.subtask_id,
                agent_name=self.name,
                success=False,
                error="No input text provided",
            )

        llm_request = LLMRequest(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a Vietnamese public service assistant. "
                        "Use the tools to help citizens find information "
                        "about government services. Always use a tool call. "
                        "Available services: cccd, passport, "
                        "business_license, land_certificate."
                    ),
                },
                {"role": "user", "content": text},
            ],
            tools=self.get_tool_schemas(),
            tool_choice="auto",
            temperature=0.0,
        )

        try:
            llm_response = await self.call_llm(llm_request)
        except Exception as exc:
            return await self._fallback_execution(request, str(exc))

        if llm_response.tool_calls:
            return await self._handle_tool_calls(request, llm_response.tool_calls)

        return AgentResponse(
            workflow_id=request.workflow_id,
            subtask_id=request.subtask_id,
            agent_name=self.name,
            success=True,
            data={"response_text": llm_response.content or "Public service query processed."},
        )

    async def _handle_tool_calls(
        self, request: AgentRequest, tool_calls: list[dict[str, Any]]
    ) -> AgentResponse:
        results: list[dict[str, Any]] = []
        response_parts: list[str] = []

        for tc in tool_calls:
            func = tc.get("function", {})
            name = func.get("name", "")
            try:
                args = json.loads(func.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}

            result = self._execute_tool(name, args)
            results.append({"tool": name, "result": result})

            if result.get("success"):
                data = result["data"]
                if name == "lookup_service" and isinstance(data, dict):
                    response_parts.append(
                        f"📋 **{data.get('name', '')}** ({data.get('name_en', '')})\n"
                        f"  🏢 Cơ quan: {data.get('agency', '')}\n"
                        f"  ⏱ Thời gian xử lý: {data.get('processing_days', '')} ngày\n"
                        f"  💰 Phí: {data.get('fee', '')}\n"
                        f"  📄 Giấy tờ cần thiết: {', '.join(data.get('required_docs', []))}\n"
                        f"  🔗 Tra cứu: {data.get('status_url', '')}"
                    )
                elif name == "list_services" and isinstance(data, list):
                    lines = [
                        f"  • {s.get('key')}: {s.get('name', '')} ({s.get('name_en', '')})"
                        for s in data
                    ]
                    response_parts.append("📋 **Dịch vụ công khả dụng:**\n" + "\n".join(lines))
                elif name == "submit_application" and isinstance(data, dict):
                    response_parts.append(
                        f"✅ Đã nộp hồ sơ: {data.get('application_id', '')}\n"
                        f"  Dịch vụ: {data.get('service', '')}\n"
                        f"  Thời gian dự kiến: {data.get('estimated_completion', '')}"
                    )
                elif name == "check_status" and isinstance(data, dict):
                    response_parts.append(
                        f"📌 Hồ sơ {data.get('application_id', '')}: {data.get('status', '')}\n"
                        f"  Nộp lúc: {data.get('submitted_at', '')}"
                    )
            else:
                response_parts.append(f"❌ {result.get('error', 'Lỗi không xác định')}")

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

    def _execute_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        try:
            if name == "lookup_service":
                service = PublicServiceDirectory.lookup_service(args.get("service_key", ""))
                if service:
                    return {"success": True, "data": service}
                return {"success": False, "error": f"Service '{args.get('service_key')}' not found"}
            elif name == "list_services":
                return {"success": True, "data": PublicServiceDirectory.list_services()}
            elif name == "submit_application":
                app = PublicServiceDirectory.submit_application(
                    service_key=args.get("service_key", ""),
                    citizen_id=args.get("citizen_id", ""),
                    notes=args.get("notes", ""),
                )
                return {"success": True, "data": app}
            elif name == "check_status":
                status = PublicServiceDirectory.check_status(args.get("application_id", ""))
                if status:
                    return {"success": True, "data": status}
                return {
                    "success": False,
                    "error": f"Application '{args.get('application_id')}' not found",
                }
            else:
                return {"success": False, "error": f"Unknown tool: {name}"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    async def _fallback_execution(self, request: AgentRequest, error: str) -> AgentResponse:
        text = request.input_data.get("text", "").lower()

        for key in PublicServiceDirectory.SERVICES:
            if key.replace("_", " ") in text or key in text:
                service = PublicServiceDirectory.SERVICES[key]
                return AgentResponse(
                    workflow_id=request.workflow_id,
                    subtask_id=request.subtask_id,
                    agent_name=self.name,
                    success=True,
                    data={
                        "response_text": (
                            f"📋 {service['name']}: cần {', '.join(service['required_docs'])}. "
                            f"Thời gian: {service['processing_days']} ngày. Phí: {service['fee']}."
                        ),
                    },
                    metadata={"fallback": True},
                )

        return AgentResponse(
            workflow_id=request.workflow_id,
            subtask_id=request.subtask_id,
            agent_name=self.name,
            success=True,
            data={
                "response_text": (
                    "Các dịch vụ công khả dụng: CCCD, Hộ chiếu, Giấy phép kinh doanh, Sổ đỏ. "
                    "Vui lòng hỏi cụ thể về dịch vụ bạn cần."
                ),
            },
            metadata={"fallback": True, "llm_error": error},
        )
