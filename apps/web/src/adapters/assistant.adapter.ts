import type {
  AssistantCapabilities,
  AssistantContextOptions,
  AssistantMessage,
  AssistantPinnedContext,
  AssistantPromptSuggestion,
  AssistantResponse,
  AssistantSession,
  AssistantSessionMessageResult,
} from "@/types";

function normalizePinnedContext(payload: any): AssistantPinnedContext {
  return {
    selectedClientId: payload?.selectedClientId ?? payload?.selected_client_id ?? null,
    selectedSkuId: payload?.selectedSkuId ?? payload?.selected_sku_id ?? null,
    selectedUploadIds: payload?.selectedUploadIds ?? payload?.selected_upload_ids ?? [],
    selectedReserveRunId: payload?.selectedReserveRunId ?? payload?.selected_reserve_run_id ?? null,
    selectedCategoryId: payload?.selectedCategoryId ?? payload?.selected_category_id ?? null,
  };
}

export function assistantResponseApiToViewModel(response: any): AssistantResponse {
  const tokenUsage = response.tokenUsage ?? response.token_usage ?? {};
  return {
    answerId: response.answerId ?? response.answer_id ?? response.id,
    sessionId: response.sessionId ?? response.session_id ?? null,
    intent: response.intent,
    status: response.status,
    confidence: response.confidence ?? 0,
    title: response.title ?? "Ответ ассистента",
    summary: response.summary ?? response.answer ?? "",
    sections: response.sections ?? [],
    sourceRefs: response.sourceRefs ?? response.source_refs ?? [],
    toolCalls: response.toolCalls ?? response.tool_calls ?? [],
    followups: response.followups ?? response.follow_ups ?? [],
    warnings: response.warnings ?? [],
    createdAt: response.generatedAt ?? response.generated_at ?? response.createdAt ?? response.created_at,
    provider: response.provider ?? "deterministic",
    tokenUsage: {
      inputTokens: tokenUsage.inputTokens ?? tokenUsage.input_tokens ?? 0,
      outputTokens: tokenUsage.outputTokens ?? tokenUsage.output_tokens ?? 0,
      totalTokens: tokenUsage.totalTokens ?? tokenUsage.total_tokens ?? 0,
      estimatedCostUsd: tokenUsage.estimatedCostUsd ?? tokenUsage.estimated_cost_usd ?? 0,
      estimatedCostRub: tokenUsage.estimatedCostRub ?? tokenUsage.estimated_cost_rub ?? 0,
    },
    traceId: response.traceId ?? response.trace_id ?? "",
    contextUsed: normalizePinnedContext(response.contextUsed ?? response.context_used ?? {}),
  };
}

export function assistantMessageApiToViewModel(message: any): AssistantMessage {
  return {
    id: message.id,
    sessionId: message.sessionId ?? message.session_id,
    role: message.role,
    text: message.text,
    createdAt: message.createdAt ?? message.created_at,
    intent: message.intent ?? null,
    status: message.status,
    provider: message.provider ?? null,
    confidence: message.confidence ?? null,
    traceId: message.traceId ?? message.trace_id ?? null,
    context: normalizePinnedContext(message.context ?? {}),
    response: message.response ? assistantResponseApiToViewModel(message.response) : null,
  };
}

export function assistantSessionApiToViewModel(session: any): AssistantSession {
  const tokenUsage = session.tokenUsage ?? session.token_usage ?? {};
  return {
    id: session.id,
    title: session.title,
    status: session.status,
    createdAt: session.createdAt ?? session.created_at,
    updatedAt: session.updatedAt ?? session.updated_at,
    lastMessageAt: session.lastMessageAt ?? session.last_message_at ?? null,
    messageCount: session.messageCount ?? session.message_count ?? 0,
    pinnedContext: normalizePinnedContext(session.pinnedContext ?? session.pinned_context ?? {}),
    lastIntent: session.lastIntent ?? session.last_intent ?? null,
    preferredMode: session.preferredMode ?? session.preferred_mode ?? "deterministic",
    provider: session.provider ?? "deterministic",
    latestTraceId: session.latestTraceId ?? session.latest_trace_id ?? null,
    tokenUsage: {
      inputTokens: tokenUsage.inputTokens ?? tokenUsage.input_tokens ?? 0,
      outputTokens: tokenUsage.outputTokens ?? tokenUsage.output_tokens ?? 0,
      totalTokens: tokenUsage.totalTokens ?? tokenUsage.total_tokens ?? 0,
      estimatedCostUsd: tokenUsage.estimatedCostUsd ?? tokenUsage.estimated_cost_usd ?? 0,
      estimatedCostRub: tokenUsage.estimatedCostRub ?? tokenUsage.estimated_cost_rub ?? session.estimatedCostRub ?? session.estimated_cost_rub ?? 0,
    },
    estimatedCostRub: session.estimatedCostRub ?? session.estimated_cost_rub ?? tokenUsage.estimatedCostRub ?? tokenUsage.estimated_cost_rub ?? 0,
  };
}

export function assistantSessionMessageResultApiToViewModel(
  result: any,
): AssistantSessionMessageResult {
  return {
    session: assistantSessionApiToViewModel(result.session),
    userMessage: assistantMessageApiToViewModel(result.userMessage ?? result.user_message),
    assistantMessage: assistantMessageApiToViewModel(
      result.assistantMessage ?? result.assistant_message,
    ),
    response: assistantResponseApiToViewModel(result.response),
  };
}

export function assistantCapabilitiesApiToViewModel(payload: any): AssistantCapabilities {
  return {
    provider: payload.provider,
    deterministicFallback:
      payload.deterministicFallback ?? payload.deterministic_fallback ?? true,
    intents: payload.intents ?? [],
    sessionSupport: payload.sessionSupport ?? payload.session_support ?? true,
    pinnedContextSupport:
      payload.pinnedContextSupport ?? payload.pinned_context_support ?? true,
  };
}

export function assistantPromptSuggestionsApiToViewModel(payload: any): AssistantPromptSuggestion[] {
  return (payload.items ?? payload ?? []).map((item: any) => ({
    id: item.id,
    label: item.label,
    prompt: item.prompt,
    intent: item.intent,
  }));
}

export function assistantContextOptionsApiToViewModel(payload: any): AssistantContextOptions {
  return {
    clients: payload.clients ?? [],
    skus: payload.skus ?? [],
    uploads: payload.uploads ?? [],
    reserveRuns: payload.reserveRuns ?? payload.reserve_runs ?? [],
    categories: payload.categories ?? [],
  };
}
