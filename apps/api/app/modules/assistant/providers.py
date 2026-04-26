from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Protocol

import httpx

from apps.api.app.core.config import Settings
from apps.api.app.modules.assistant.domain import (
    AssistantAnswerDraft,
    AssistantRoutePlan,
    AssistantTokenUsageData,
    AssistantWarningData,
)
from apps.api.app.modules.assistant.schemas import AssistantIntent


class AssistantProviderError(RuntimeError):
    pass


PLANNABLE_INTENTS: set[str] = {
    "reserve_calculation",
    "reserve_explanation",
    "stock_risk_summary",
    "inbound_impact",
    "diy_coverage_check",
    "sku_summary",
    "client_summary",
    "upload_status_summary",
    "quality_issue_summary",
    "management_report_summary",
    "free_chat",
    "unsupported_or_ambiguous",
}

PLANNABLE_TOOLS: set[str] = {
    "calculate_reserve",
    "get_reserve_explanation",
    "get_sku_summary",
    "get_client_summary",
    "get_inbound_impact",
    "get_stock_coverage",
    "get_upload_status",
    "get_quality_issues",
    "get_dashboard_summary",
    "get_management_report",
}


class AssistantProvider(Protocol):
    name: str

    def finalize(self, draft: AssistantAnswerDraft) -> AssistantAnswerDraft: ...


def _empty_usage() -> AssistantTokenUsageData:
    return AssistantTokenUsageData()


def _usage_from_response(payload: dict[str, Any], settings: Settings) -> AssistantTokenUsageData:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return _empty_usage()
    input_tokens = int(
        usage.get("prompt_tokens")
        or usage.get("input_tokens")
        or usage.get("inputTokens")
        or 0
    )
    output_tokens = int(
        usage.get("completion_tokens")
        or usage.get("output_tokens")
        or usage.get("outputTokens")
        or 0
    )
    total_tokens = int(usage.get("total_tokens") or usage.get("totalTokens") or input_tokens + output_tokens)
    cost_usd = (
        input_tokens / 1_000_000 * settings.assistant_input_usd_per_1m_tokens
        + output_tokens / 1_000_000 * settings.assistant_output_usd_per_1m_tokens
    )
    return AssistantTokenUsageData(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=round(cost_usd, 8),
        estimated_cost_rub=round(cost_usd * settings.assistant_rub_per_usd, 4),
    )


def combine_token_usage(*items: AssistantTokenUsageData) -> AssistantTokenUsageData:
    input_tokens = sum(item.input_tokens for item in items)
    output_tokens = sum(item.output_tokens for item in items)
    total_tokens = sum(item.total_tokens for item in items)
    cost_usd = sum(item.estimated_cost_usd for item in items)
    cost_rub = sum(item.estimated_cost_rub for item in items)
    return AssistantTokenUsageData(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=round(cost_usd, 8),
        estimated_cost_rub=round(cost_rub, 4),
    )


def _draft_payload(draft: AssistantAnswerDraft) -> dict[str, Any]:
    return {
        "intent": draft.intent,
        "status": draft.status,
        "confidence": draft.confidence,
        "title": draft.title,
        "summary": draft.summary,
        "sections": draft.sections,
        "warnings": [
            {"code": warning.code, "message": warning.message, "severity": warning.severity}
            for warning in draft.warnings
        ],
        "followups": draft.followups,
        "sourceRefs": draft.source_refs,
        "toolCalls": [
            {
                "toolName": tool.tool_name,
                "status": tool.status,
                "summary": tool.summary,
                "arguments": tool.arguments,
                "latencyMs": tool.latency_ms,
            }
            for tool in draft.tool_calls
        ],
        "userText": draft.user_text,
    }


def _apply_response(draft: AssistantAnswerDraft, payload: dict[str, Any]) -> AssistantAnswerDraft:
    result = deepcopy(draft)
    title = str(payload.get("title") or "").strip()
    summary = str(payload.get("summary") or "").strip()
    if title:
        result.title = title
    if summary:
        result.summary = summary
    section_updates = payload.get("sections")
    if isinstance(section_updates, list):
        updates_by_id = {
            str(item.get("id")): item for item in section_updates if isinstance(item, dict) and item.get("id")
        }
        updated_sections: list[dict[str, Any]] = []
        for section in result.sections:
            next_section = dict(section)
            update = updates_by_id.get(str(section.get("id")))
            if update:
                if isinstance(update.get("title"), str) and update["title"].strip():
                    next_section["title"] = update["title"].strip()
                if isinstance(update.get("body"), str) and update["body"].strip():
                    next_section["body"] = update["body"].strip()
                if (
                    section.get("type") not in {"metric_summary", "reserve_table_preview"}
                    and isinstance(update.get("items"), list)
                    and update["items"]
                ):
                    next_section["items"] = [str(item) for item in update["items"] if str(item).strip()]
            updated_sections.append(next_section)
        result.sections = updated_sections
    return result


class DeterministicAssistantProvider:
    name = "deterministic"

    def finalize(self, draft: AssistantAnswerDraft) -> AssistantAnswerDraft:
        return draft


class OpenAICompatibleAssistantProvider:
    name = "openai_compatible"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _endpoint(self) -> str:
        if not self._settings.assistant_llm_enabled:
            raise AssistantProviderError("LLM-провайдер отключён конфигурацией.")
        if not self._settings.assistant_openai_base_url:
            raise AssistantProviderError("Не задан assistant_openai_base_url.")
        if not self._settings.assistant_openai_api_key:
            raise AssistantProviderError("Не задан assistant_openai_api_key.")
        return self._settings.assistant_openai_base_url.rstrip("/") + "/chat/completions"

    def _request_payload(self, draft: AssistantAnswerDraft) -> dict[str, Any]:
        if draft.intent == "free_chat":
            system_prompt = (
                "Ты доменно-ограниченный чат-ассистент MAGAMAX внутри премиального internal analytics продукта. "
                "Отвечай только по работе с MAGAMAX, загруженным данным, ingestion, mapping, quality, "
                "резервам, SKU, клиентам DIY, складу, входящим поставкам, dashboard и расчётам по этим данным. "
                "Если сообщение выходит за этот контур, верни жёсткий отказ: "
                "«Шайтан-машина отвечает только на вопросы, сопряжённые с рабочими данными MAGAMAX». "
                "Если пользователь просит операционные факты, числа или выводы, не выдумывай их: "
                "предложи сформулировать вопрос так, чтобы включились реальные инструменты продукта. "
                "Можно использовать только переданный JSON-контекст и закреплённый контекст сессии. "
                "Верни JSON со структурой {title, summary, sections:[{id, title?, body?, items?}]}. "
                "Сохраняй id секций из draft, не добавляй markdown."
            )
            task = "Сформируй короткий человеческий ответ в режиме свободного чата, без технических пояснений про tools."
        else:
            system_prompt = (
                "Ты редактор ответов для премиального internal analytics продукта. "
                "Нельзя придумывать новые факты. Используй только предоставленный JSON-контекст. "
                "Верни JSON со структурой {title, summary, sections:[{id, title?, body?, items?}]}. "
                "Пиши кратко, по-русски, спокойно, без маркетингового тона."
            )
            task = (
                "Сделай формулировки более ясными и краткими, "
                "не меняя смысл, числа, источники и предупреждения."
            )
        return {
            "model": self._settings.assistant_openai_model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "task": task,
                            "draft": _draft_payload(draft),
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }

    def _planning_payload(
        self,
        *,
        question: str,
        deterministic_intent: str,
        history: list[dict[str, Any]],
    ) -> dict[str, Any]:
        system_prompt = (
            "Ты LLM-оркестратор MAGAMAX. Сначала интерпретируй любой запрос пользователя, затем "
            "выбери доменный intent и allowlisted инструменты, которые должны получить данные из БД. "
            "Не отвечай на вопрос сам. Не придумывай данные. Не вычисляй числа внутри LLM. "
            "Если запрос касается работы MAGAMAX даже косвенно — загрузок, отчётов, продаж, "
            "товаров, товарных групп, прибыли, рентабельности, выручки, подразделений, SKU, "
            "склада, поставок, резервов, качества данных или dashboard — выбери ближайший доменный intent. "
            "Если вопрос явно про управленческий отчёт, 2025, товарные группы, прибыль, рентабельность "
            "или выручку, чаще всего нужен intent management_report_summary и tool get_management_report. "
            "Выбери ровно один intent из allowedIntents и инструменты только из allowedTools. "
            "При необходимости перепиши toolQuestion так, чтобы backend-роутер извлёк параметры "
            "или follow-up использовал предыдущий контекст чата. "
            "Если пользователь пишет «подробнее», «дай развернутые данные», «покажи детали», "
            "и предыдущее сообщение ассистента было доменным ответом, наследуй предыдущий intent. "
            "Если вопрос вне рабочего контура MAGAMAX, выбери unsupported_or_ambiguous и пустой список toolNames. "
            "Верни только JSON: {intent, confidence, toolQuestion, toolNames, rationale}. "
            "toolQuestion должен содержать исходный смысл и нужный предыдущий контекст, но не новые факты."
        )
        return {
            "model": self._settings.assistant_openai_model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "question": question,
                            "deterministicIntent": deterministic_intent,
                            "allowedIntents": sorted(PLANNABLE_INTENTS),
                            "allowedTools": sorted(PLANNABLE_TOOLS),
                            "recentHistory": history[-8:],
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }

    def plan_route(
        self,
        *,
        question: str,
        deterministic_intent: str,
        history: list[dict[str, Any]],
    ) -> AssistantRoutePlan:
        endpoint = self._endpoint()
        try:
            with httpx.Client(timeout=8.0) as client:
                response = client.post(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {self._settings.assistant_openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=self._planning_payload(
                        question=question,
                        deterministic_intent=deterministic_intent,
                        history=history,
                    ),
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AssistantProviderError(f"HTTP-ошибка planner-провайдера: {exc}") from exc

        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise TypeError("Провайдер вернул неожиданный planner content.")
            structured = json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise AssistantProviderError("Провайдер вернул неподдерживаемый planner-формат.") from exc
        if not isinstance(structured, dict):
            raise AssistantProviderError("Провайдер вернул некорректный planner JSON.")

        intent = str(structured.get("intent") or "").strip()
        if intent not in PLANNABLE_INTENTS:
            raise AssistantProviderError("Провайдер вернул неизвестный intent.")
        tool_question = str(structured.get("toolQuestion") or "").strip() or None
        raw_tools = structured.get("toolNames")
        tool_names: list[str] = []
        if isinstance(raw_tools, list):
            for item in raw_tools:
                tool_name = str(item or "").strip()
                if tool_name in PLANNABLE_TOOLS and tool_name not in tool_names:
                    tool_names.append(tool_name)
        rationale = str(structured.get("rationale") or "").strip() or None
        try:
            confidence = float(structured.get("confidence") or 0)
        except (TypeError, ValueError):
            confidence = 0
        return AssistantRoutePlan(
            intent=intent,  # type: ignore[arg-type]
            tool_question=tool_question,
            tool_names=tool_names,
            confidence=max(min(confidence, 1.0), 0.0),
            planner=self.name,
            rationale=rationale,
            token_usage=_usage_from_response(payload, self._settings),
        )

    def finalize(self, draft: AssistantAnswerDraft) -> tuple[AssistantAnswerDraft, AssistantTokenUsageData]:
        endpoint = self._endpoint()
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {self._settings.assistant_openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=self._request_payload(draft),
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AssistantProviderError(f"HTTP-ошибка провайдера: {exc}") from exc

        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise TypeError("Провайдер вернул неожиданный content.")
            structured = json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise AssistantProviderError("Провайдер вернул неподдерживаемый формат ответа.") from exc

        if not isinstance(structured, dict):
            raise AssistantProviderError("Провайдер вернул некорректный JSON-объект.")
        return _apply_response(draft, structured), _usage_from_response(payload, self._settings)


def plan_route_with_provider(
    settings: Settings,
    *,
    question: str,
    deterministic_intent: AssistantIntent,
    history: list[dict[str, Any]] | None = None,
) -> AssistantRoutePlan:
    if settings.assistant_provider != "openai_compatible" or not settings.assistant_llm_enabled:
        return AssistantRoutePlan(intent=deterministic_intent, tool_question=question)

    provider = OpenAICompatibleAssistantProvider(settings)
    try:
        return provider.plan_route(
            question=question,
            deterministic_intent=deterministic_intent,
            history=history or [],
        )
    except AssistantProviderError:
        # Planning failure must not break deterministic tool execution.
        return AssistantRoutePlan(intent=deterministic_intent, tool_question=question)


def finalize_with_provider(
    settings: Settings,
    draft: AssistantAnswerDraft,
) -> tuple[AssistantAnswerDraft, str, list[AssistantWarningData], AssistantTokenUsageData]:
    if draft.intent == "unsupported_or_ambiguous" or draft.status == "unsupported":
        provider = DeterministicAssistantProvider()
        return provider.finalize(draft), provider.name, [], _empty_usage()
    if settings.assistant_provider == "openai_compatible":
        provider = OpenAICompatibleAssistantProvider(settings)
        try:
            finalized, usage = provider.finalize(draft)
            return finalized, provider.name, [], usage
        except AssistantProviderError:
            warning = AssistantWarningData(
                code="provider_unavailable",
                message="LLM-провайдер недоступен, использован детерминированный режим.",
                severity="warning",
            )
            draft.warnings.append(warning)
    provider = DeterministicAssistantProvider()
    return provider.finalize(draft), provider.name, [
        warning for warning in draft.warnings if warning.code == "provider_unavailable"
    ], _empty_usage()
