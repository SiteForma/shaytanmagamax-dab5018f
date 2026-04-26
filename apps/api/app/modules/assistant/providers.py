from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Protocol

import httpx

from apps.api.app.core.config import Settings
from apps.api.app.modules.assistant.domain import AssistantAnswerDraft, AssistantWarningData


class AssistantProviderError(RuntimeError):
    pass


class AssistantProvider(Protocol):
    name: str

    def finalize(self, draft: AssistantAnswerDraft) -> AssistantAnswerDraft: ...


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
                if isinstance(update.get("items"), list) and update["items"]:
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
        return {
            "model": self._settings.assistant_openai_model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Ты редактор ответов для премиального internal analytics продукта. "
                        "Нельзя придумывать новые факты. Используй только предоставленный JSON-контекст. "
                        "Верни JSON со структурой {title, summary, sections:[{id, title?, body?, items?}]}. "
                        "Пиши кратко, по-русски, спокойно, без маркетингового тона."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "task": (
                                "Сделай формулировки более ясными и краткими, "
                                "не меняя смысл, числа, источники и предупреждения."
                            ),
                            "draft": _draft_payload(draft),
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }

    def finalize(self, draft: AssistantAnswerDraft) -> AssistantAnswerDraft:
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
        return _apply_response(draft, structured)


def finalize_with_provider(
    settings: Settings,
    draft: AssistantAnswerDraft,
) -> tuple[AssistantAnswerDraft, str, list[AssistantWarningData]]:
    if settings.assistant_provider == "openai_compatible":
        provider = OpenAICompatibleAssistantProvider(settings)
        try:
            return provider.finalize(draft), provider.name, []
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
    ]
