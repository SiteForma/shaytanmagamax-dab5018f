from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from apps.api.app.common.schemas import ORMModel

AssistantIntent = Literal[
    "reserve_calculation",
    "reserve_explanation",
    "stock_risk_summary",
    "inbound_impact",
    "diy_coverage_check",
    "sku_summary",
    "client_summary",
    "upload_status_summary",
    "quality_issue_summary",
    "unsupported_or_ambiguous",
]
AssistantResponseStatus = Literal[
    "completed",
    "partial",
    "needs_clarification",
    "unsupported",
    "failed",
]
AssistantSectionType = Literal[
    "narrative",
    "metric_summary",
    "reserve_table_preview",
    "source_list",
    "warning_block",
    "next_actions",
]
AssistantFollowupAction = Literal["query", "open"]
AssistantSourceRole = Literal["primary", "supporting", "warning"]


class AssistantPinnedContext(ORMModel):
    selected_client_id: str | None = Field(default=None, alias="selectedClientId")
    selected_sku_id: str | None = Field(default=None, alias="selectedSkuId")
    selected_upload_ids: list[str] = Field(default_factory=list, alias="selectedUploadIds")
    selected_reserve_run_id: str | None = Field(default=None, alias="selectedReserveRunId")
    selected_category_id: str | None = Field(default=None, alias="selectedCategoryId")

    # Compatibility aliases for the existing UI shell.
    selected_client: str | None = Field(default=None, alias="selectedClient")
    selected_sku: str | None = Field(default=None, alias="selectedSku")
    selected_files: list[str] | None = Field(default=None, alias="selectedFiles")
    selected_category: str | None = Field(default=None, alias="selectedCategory")

    def normalized(self) -> "AssistantPinnedContext":
        return AssistantPinnedContext(
            selectedClientId=self.selected_client_id or self.selected_client,
            selectedSkuId=self.selected_sku_id or self.selected_sku,
            selectedUploadIds=list(self.selected_upload_ids or self.selected_files or []),
            selectedReserveRunId=self.selected_reserve_run_id,
            selectedCategoryId=self.selected_category_id or self.selected_category,
        )


class AssistantSessionCreateRequest(ORMModel):
    title: str | None = None
    preferred_mode: str = Field(default="deterministic", alias="preferredMode")
    pinned_context: AssistantPinnedContext | None = Field(default=None, alias="pinnedContext")


class AssistantSessionUpdateRequest(ORMModel):
    title: str | None = None
    status: Literal["active", "archived"] | None = None
    preferred_mode: str | None = Field(default=None, alias="preferredMode")
    pinned_context: AssistantPinnedContext | None = Field(default=None, alias="pinnedContext")


class AssistantQueryRequest(ORMModel):
    text: str | None = None
    question: str | None = None
    session_id: str | None = Field(default=None, alias="sessionId")
    preferred_mode: str = Field(default="deterministic", alias="preferredMode")
    context: AssistantPinnedContext | None = None

    def prompt_text(self) -> str:
        return (self.text or self.question or "").strip()


class AssistantMessageCreateRequest(ORMModel):
    text: str
    preferred_mode: str = Field(default="deterministic", alias="preferredMode")
    context: AssistantPinnedContext | None = None


class AssistantWarning(ORMModel):
    code: str
    message: str
    severity: Literal["info", "warning", "error"] = "warning"


class AssistantSourceRef(ORMModel):
    source_type: str = Field(alias="sourceType")
    source_label: str = Field(alias="sourceLabel")
    entity_type: str = Field(alias="entityType")
    entity_id: str | None = Field(default=None, alias="entityId")
    external_key: str | None = Field(default=None, alias="externalKey")
    freshness_at: str | None = Field(default=None, alias="freshnessAt")
    role: AssistantSourceRole = "supporting"
    route: str | None = None
    detail: str | None = None


class AssistantToolCall(ORMModel):
    tool_name: str = Field(alias="toolName")
    status: Literal["completed", "failed", "skipped"]
    arguments: dict[str, Any]
    summary: str
    latency_ms: int = Field(alias="latencyMs")


class AssistantMetric(ORMModel):
    key: str
    label: str
    value: str
    tone: Literal["neutral", "warning", "critical", "positive"] = "neutral"


class AssistantAnswerSection(ORMModel):
    id: str
    type: AssistantSectionType
    title: str
    body: str | None = None
    metrics: list[AssistantMetric] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    items: list[str] = Field(default_factory=list)


class AssistantFollowupSuggestion(ORMModel):
    id: str
    label: str
    prompt: str
    action: AssistantFollowupAction = "query"
    route: str | None = None


class AssistantResponse(ORMModel):
    answer_id: str = Field(alias="answerId")
    session_id: str | None = Field(default=None, alias="sessionId")
    intent: AssistantIntent
    status: AssistantResponseStatus
    confidence: float
    title: str
    summary: str
    sections: list[AssistantAnswerSection]
    source_refs: list[AssistantSourceRef] = Field(alias="sourceRefs")
    tool_calls: list[AssistantToolCall] = Field(alias="toolCalls")
    followups: list[AssistantFollowupSuggestion]
    warnings: list[AssistantWarning]
    generated_at: str = Field(alias="generatedAt")
    trace_id: str = Field(alias="traceId")
    provider: str
    context_used: AssistantPinnedContext = Field(alias="contextUsed")


class AssistantMessageResponse(ORMModel):
    id: str
    session_id: str = Field(alias="sessionId")
    role: Literal["user", "assistant"]
    text: str
    created_at: str = Field(alias="createdAt")
    intent: AssistantIntent | None = None
    status: str
    provider: str | None = None
    confidence: float | None = None
    trace_id: str | None = Field(default=None, alias="traceId")
    context: AssistantPinnedContext = Field(default_factory=AssistantPinnedContext)
    response: AssistantResponse | None = None


class AssistantSessionSummary(ORMModel):
    id: str
    title: str
    status: str
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    last_message_at: str | None = Field(default=None, alias="lastMessageAt")
    message_count: int = Field(alias="messageCount")
    pinned_context: AssistantPinnedContext = Field(alias="pinnedContext")
    last_intent: AssistantIntent | None = Field(default=None, alias="lastIntent")
    preferred_mode: str = Field(alias="preferredMode")
    provider: str
    latest_trace_id: str | None = Field(default=None, alias="latestTraceId")


class AssistantSessionDetail(AssistantSessionSummary):
    messages: list[AssistantMessageResponse] = Field(default_factory=list)


class AssistantSessionMessageResult(ORMModel):
    session: AssistantSessionSummary
    user_message: AssistantMessageResponse = Field(alias="userMessage")
    assistant_message: AssistantMessageResponse = Field(alias="assistantMessage")
    response: AssistantResponse


class AssistantCapability(ORMModel):
    key: str
    label: str
    supported: bool = True


class AssistantCapabilitiesResponse(ORMModel):
    provider: str
    deterministic_fallback: bool = Field(alias="deterministicFallback")
    intents: list[AssistantCapability]
    session_support: bool = Field(alias="sessionSupport")
    pinned_context_support: bool = Field(alias="pinnedContextSupport")


class AssistantPromptSuggestion(ORMModel):
    id: str
    label: str
    prompt: str
    intent: AssistantIntent


class AssistantPromptSuggestionsResponse(ORMModel):
    items: list[AssistantPromptSuggestion]


class AssistantContextOption(ORMModel):
    id: str
    label: str
    hint: str | None = None


class AssistantContextOptionsResponse(ORMModel):
    clients: list[AssistantContextOption]
    skus: list[AssistantContextOption]
    uploads: list[AssistantContextOption]
    reserve_runs: list[AssistantContextOption] = Field(alias="reserveRuns")
    categories: list[AssistantContextOption]
