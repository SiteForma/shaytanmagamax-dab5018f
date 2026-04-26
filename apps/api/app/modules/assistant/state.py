from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any


@dataclass(slots=True)
class AssistantMissingField:
    name: str
    label: str
    question: str
    field_type: str = "string"

    def to_payload(self) -> dict[str, str]:
        return {
            "name": self.name,
            "label": self.label,
            "question": self.question,
            "type": self.field_type,
        }


@dataclass(slots=True)
class AssistantEntityState:
    client_id: str | None = None
    client_name: str | None = None
    sku_id: str | None = None
    sku_ids: list[str] = field(default_factory=list)
    sku_codes: list[str] = field(default_factory=list)
    category_id: str | None = None
    category_name: str | None = None
    upload_ids: list[str] = field(default_factory=list)
    reserve_run_id: str | None = None

    def to_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if self.client_id:
            params["client_id"] = self.client_id
        if self.client_name:
            params["client_name"] = self.client_name
        if self.sku_id:
            params["sku_id"] = self.sku_id
        if self.sku_ids:
            params["sku_ids"] = list(self.sku_ids)
        if self.sku_codes:
            params["sku_codes"] = list(self.sku_codes)
        if self.category_id:
            params["category_id"] = self.category_id
        if self.category_name:
            params["category_name"] = self.category_name
        if self.upload_ids:
            params["upload_ids"] = list(self.upload_ids)
        if self.reserve_run_id:
            params["reserve_run_id"] = self.reserve_run_id
        return params


@dataclass(slots=True)
class AssistantSessionState:
    last_intent: str | None = None
    last_entities: AssistantEntityState = field(default_factory=AssistantEntityState)
    last_filters: dict[str, Any] = field(default_factory=dict)
    last_tool_name: str | None = None
    last_result_ref: dict[str, Any] | None = None
    missing_fields: list[AssistantMissingField] = field(default_factory=list)
    pending_intent: str | None = None
    pending_question: str | None = None
    comparison_base: dict[str, Any] = field(default_factory=dict)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _field_from_payload(value: Any) -> AssistantMissingField | None:
    if isinstance(value, str) and value.strip():
        name = value.strip()
        return AssistantMissingField(name=name, label=name, question=f"Уточните {name}.")
    if not isinstance(value, dict):
        return None
    name = str(value.get("name") or value.get("field") or "").strip()
    if not name:
        return None
    return AssistantMissingField(
        name=name,
        label=str(value.get("label") or name),
        question=str(value.get("question") or f"Уточните {name}."),
        field_type=str(value.get("type") or value.get("fieldType") or "string"),
    )


def _entities_from_args(args: dict[str, Any]) -> AssistantEntityState:
    sku_ids = args.get("sku_ids")
    upload_ids = args.get("upload_ids")
    return AssistantEntityState(
        client_id=str(args.get("client_id") or "") or None,
        sku_id=str(args.get("sku_id") or "") or None,
        sku_ids=[str(item) for item in _as_list(sku_ids) if str(item).strip()],
        category_id=str(args.get("category_id") or "") or None,
        upload_ids=[str(item) for item in _as_list(upload_ids) if str(item).strip()],
        reserve_run_id=str(args.get("run_id") or args.get("reserve_run_id") or "") or None,
    )


def _merge_entities(base: AssistantEntityState, incoming: AssistantEntityState) -> AssistantEntityState:
    merged = replace(base)
    for attr in ("client_id", "client_name", "sku_id", "category_id", "category_name", "reserve_run_id"):
        value = getattr(incoming, attr)
        if value:
            setattr(merged, attr, value)
    if incoming.sku_ids:
        merged.sku_ids = list(dict.fromkeys(incoming.sku_ids))
    if incoming.sku_codes:
        merged.sku_codes = list(dict.fromkeys(incoming.sku_codes))
    if incoming.upload_ids:
        merged.upload_ids = list(dict.fromkeys(incoming.upload_ids))
    return merged


def _primary_source_ref(source_refs: list[Any]) -> dict[str, Any] | None:
    refs = [_as_dict(item) for item in source_refs]
    primary = next((item for item in refs if item.get("role") == "primary"), None)
    return primary or (refs[0] if refs else None)


def derive_state_from_history(history: list[dict[str, Any]] | None) -> AssistantSessionState:
    state = AssistantSessionState()
    for item in history or []:
        response = _as_dict(item.get("response") or item)
        role = str(item.get("role") or response.get("role") or "")
        intent = str(item.get("intent") or response.get("intent") or "") or None
        status = str(item.get("status") or response.get("status") or "")

        if role == "assistant" and (
            response.get("type") == "clarification" or status == "needs_clarification"
        ):
            fields = [
                field
                for field in (_field_from_payload(value) for value in _as_list(response.get("missingFields")))
                if field is not None
            ]
            state.missing_fields = fields
            state.pending_intent = str(response.get("pendingIntent") or intent or "") or None
            state.pending_question = str(response.get("summary") or item.get("text") or "") or None
            continue

        if role != "assistant" or intent in {None, "", "free_chat", "unsupported_or_ambiguous"}:
            continue

        state.last_intent = intent
        state.pending_intent = None
        state.pending_question = None
        state.missing_fields = []

        source_ref = _primary_source_ref(_as_list(item.get("sourceRefs") or response.get("sourceRefs")))
        if source_ref:
            state.last_result_ref = source_ref
            if source_ref.get("entityType") == "reserve_run":
                state.last_entities.reserve_run_id = str(source_ref.get("entityId") or "") or None

        tool_calls = _as_list(item.get("toolCalls") or response.get("toolCalls"))
        if tool_calls:
            primary_tool = _as_dict(tool_calls[0])
            state.last_tool_name = str(primary_tool.get("toolName") or "") or None
            combined_args: dict[str, Any] = {}
            for tool_call in tool_calls:
                args = _as_dict(_as_dict(tool_call).get("arguments"))
                combined_args.update(
                    {key: value for key, value in args.items() if value not in (None, "", [])}
                )
            state.last_filters = combined_args
            state.last_entities = _merge_entities(state.last_entities, _entities_from_args(combined_args))
            if intent in {"sales_summary", "period_comparison", "management_report_summary"}:
                state.comparison_base = {"intent": intent, **combined_args}
    return state


def merge_state(
    state: AssistantSessionState,
    *,
    intent: str | None = None,
    params: dict[str, Any] | None = None,
    missing_fields: list[AssistantMissingField] | None = None,
    pending_question: str | None = None,
) -> AssistantSessionState:
    next_state = replace(state)
    next_state.last_entities = replace(state.last_entities)
    next_state.last_filters = dict(state.last_filters)
    next_state.comparison_base = dict(state.comparison_base)

    if intent:
        if missing_fields:
            next_state.pending_intent = intent
            next_state.pending_question = pending_question
        else:
            next_state.last_intent = intent
            next_state.pending_intent = None
            next_state.pending_question = None
    if params:
        next_state.last_filters.update(params)
        next_state.last_entities = _merge_entities(next_state.last_entities, _entities_from_args(params))
    next_state.missing_fields = list(missing_fields or [])
    return next_state


def resolve_followup_from_state(
    question: str,
    state: AssistantSessionState,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved = dict(params or {})
    q = question.lower().strip()

    if state.pending_intent and state.missing_fields:
        resolved.setdefault("_pending_intent", state.pending_intent)

    if any(token in q for token in ("почему", "why", "объясни")):
        for key, value in state.last_entities.to_params().items():
            resolved.setdefault(key, value)
        if state.last_intent:
            if state.last_intent in {"reserve_calculation", "reserve_explanation"}:
                resolved.setdefault("_followup_intent", "reserve_explanation")
            else:
                resolved.setdefault("_followup_intent", state.last_intent)

    if q.startswith("а по ") or q.startswith("а для "):
        for key, value in state.last_filters.items():
            resolved.setdefault(key, value)
        if state.last_intent:
            resolved.setdefault("_followup_intent", state.last_intent)

    if any(token in q for token in ("только проблем", "проблемные", "critical", "критич")):
        for key, value in state.last_entities.to_params().items():
            resolved.setdefault(key, value)
        for key, value in state.last_filters.items():
            resolved.setdefault(key, value)
        if state.last_intent:
            resolved.setdefault("_followup_intent", state.last_intent)

    if "прошлым месяц" in q or "прошлый месяц" in q:
        metric = state.comparison_base.get("metric")
        if metric:
            resolved.setdefault("metric", metric)
        if state.last_intent:
            resolved.setdefault("_followup_intent", "period_comparison")
    return resolved
