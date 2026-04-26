from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from apps.api.app.modules.assistant.schemas import AssistantIntent


@dataclass(slots=True)
class AssistantWarningData:
    code: str
    message: str
    severity: str = "warning"


@dataclass(slots=True)
class AssistantTokenUsageData:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    estimated_cost_rub: float = 0.0


@dataclass(slots=True)
class AssistantRoute:
    intent: AssistantIntent
    extracted_client_id: str | None = None
    extracted_client_name: str | None = None
    extracted_sku_ids: list[str] = field(default_factory=list)
    extracted_sku_codes: list[str] = field(default_factory=list)
    extracted_upload_ids: list[str] = field(default_factory=list)
    extracted_category_id: str | None = None
    extracted_category_name: str | None = None
    reserve_months: int | None = None
    safety_factor: float | None = None
    include_inbound: bool = True
    warnings: list[AssistantWarningData] = field(default_factory=list)


@dataclass(slots=True)
class AssistantRoutePlan:
    intent: AssistantIntent | None = None
    tool_question: str | None = None
    tool_name: str | None = None
    tool_names: list[str] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)
    missing_fields: list[dict[str, Any]] = field(default_factory=list)
    followup_question: str | None = None
    confidence: float = 0.0
    planner: str = "deterministic"
    rationale: str | None = None
    token_usage: AssistantTokenUsageData = field(default_factory=AssistantTokenUsageData)


@dataclass(slots=True)
class AssistantResolvedContext:
    selected_client_id: str | None = None
    selected_sku_id: str | None = None
    selected_upload_ids: list[str] = field(default_factory=list)
    selected_reserve_run_id: str | None = None
    selected_category_id: str | None = None


@dataclass(slots=True)
class AssistantContextBundle:
    context: AssistantResolvedContext
    route: AssistantRoute
    warnings: list[AssistantWarningData] = field(default_factory=list)
    data_freshness_at: datetime | None = None


@dataclass(slots=True)
class AssistantToolExecution:
    tool_name: str
    status: str
    arguments: dict[str, Any]
    summary: str
    latency_ms: int
    payload: Any = None
    warnings: list[AssistantWarningData] = field(default_factory=list)
    source_refs: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class AssistantAnswerDraft:
    intent: AssistantIntent
    status: str
    confidence: float
    title: str
    summary: str
    sections: list[dict[str, Any]]
    source_refs: list[dict[str, Any]]
    tool_calls: list[AssistantToolExecution]
    followups: list[dict[str, Any]]
    warnings: list[AssistantWarningData]
    context_used: AssistantResolvedContext
    user_text: str | None = None
    response_type: str = "answer"
    missing_fields: list[dict[str, Any]] = field(default_factory=list)
    suggested_chips: list[str] = field(default_factory=list)
    pending_intent: str | None = None
    trace_metadata: dict[str, Any] = field(default_factory=dict)
