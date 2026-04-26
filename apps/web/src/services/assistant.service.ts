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
import {
  assistantCapabilitiesApiToViewModel,
  assistantContextOptionsApiToViewModel,
  assistantPromptSuggestionsApiToViewModel,
  assistantResponseApiToViewModel,
  assistantSessionApiToViewModel,
  assistantSessionMessageResultApiToViewModel,
  assistantMessageApiToViewModel,
} from "@/adapters/assistant.adapter";
import { api } from "@/lib/api/client";

export interface AssistantPayload {
  text: string;
  sessionId?: string;
  preferredMode?: string;
  context?: AssistantPinnedContext;
}

export type AssistantStreamEvent =
  | { type: "thinking"; sessionId?: string; stage?: string; message: string; userMessage?: AssistantMessage }
  | {
      type: "clarification";
      messageId: string;
      responseId: string;
      intent: AssistantResponse["intent"];
      summary: string;
      missingFields: AssistantResponse["missingFields"];
      suggestedChips: string[];
      pendingIntent: AssistantResponse["pendingIntent"];
    }
  | {
      type: "tool_call";
      messageId: string;
      responseId: string;
      toolName: string;
      arguments: Record<string, unknown>;
    }
  | {
      type: "tool_result";
      messageId: string;
      responseId: string;
      toolName: string;
      status: AssistantResponse["toolCalls"][number]["status"];
      summary: string;
      latencyMs: number;
    }
  | { type: "answer_delta"; messageId: string; responseId?: string; delta: string }
  | { type: "done"; result: AssistantSessionMessageResult }
  | { type: "error"; code: string; message: string };

function assistantStreamEventApiToViewModel(event: any): AssistantStreamEvent {
  if (event.type === "thinking") {
    return {
      type: "thinking",
      sessionId: event.sessionId,
      stage: event.stage,
      message: event.message ?? "",
      userMessage: event.userMessage ? assistantMessageApiToViewModel(event.userMessage) : undefined,
    };
  }
  if (event.type === "clarification") {
    return {
      type: "clarification",
      messageId: event.messageId,
      responseId: event.responseId,
      intent: event.intent,
      summary: event.summary ?? "",
      missingFields: event.missingFields ?? [],
      suggestedChips: event.suggestedChips ?? [],
      pendingIntent: event.pendingIntent ?? null,
    };
  }
  if (event.type === "done" || event.type === "final") {
    return {
      type: "done",
      result: assistantSessionMessageResultApiToViewModel(event.result),
    };
  }
  if (event.type === "assistant_delta") {
    return {
      type: "answer_delta",
      messageId: event.messageId,
      responseId: event.responseId,
      delta: event.delta ?? "",
    };
  }
  if (event.type === "status") {
    return {
      type: "thinking",
      stage: event.status,
      message: event.message ?? "",
    };
  }
  if (event.type === "user_message") {
    return {
      type: "thinking",
      message: "Сообщение сохранено.",
      userMessage: assistantMessageApiToViewModel(event.message),
    };
  }
  return event as AssistantStreamEvent;
}

export interface CreateAssistantSessionPayload {
  title?: string;
  preferredMode?: string;
  pinnedContext?: AssistantPinnedContext;
}

export interface UpdateAssistantSessionPayload {
  title?: string;
  status?: "active" | "archived";
  preferredMode?: string;
  pinnedContext?: AssistantPinnedContext;
}

export async function askAssistant(payload: AssistantPayload): Promise<AssistantResponse> {
  const response = await api.post<any>("/assistant/query", {
    text: payload.text,
    sessionId: payload.sessionId,
    preferredMode: payload.preferredMode ?? "deterministic",
    context: payload.context,
  });
  return assistantResponseApiToViewModel(response);
}

export async function createAssistantSession(
  payload: CreateAssistantSessionPayload,
): Promise<AssistantSession> {
  const response = await api.post<any>("/assistant/sessions", {
    title: payload.title,
    preferredMode: payload.preferredMode ?? "deterministic",
    pinnedContext: payload.pinnedContext,
  });
  return assistantSessionApiToViewModel(response);
}

export async function listAssistantSessions(): Promise<AssistantSession[]> {
  const response = await api.get<any[]>("/assistant/sessions");
  return response.map(assistantSessionApiToViewModel);
}

export async function getAssistantSession(sessionId: string): Promise<AssistantSession> {
  const response = await api.get<any>(`/assistant/sessions/${sessionId}`);
  return assistantSessionApiToViewModel(response);
}

export async function updateAssistantSession(
  sessionId: string,
  payload: UpdateAssistantSessionPayload,
): Promise<AssistantSession> {
  const response = await api.patch<any>(`/assistant/sessions/${sessionId}`, {
    title: payload.title,
    status: payload.status,
    preferredMode: payload.preferredMode,
    pinnedContext: payload.pinnedContext,
  });
  return assistantSessionApiToViewModel(response);
}

export async function deleteAssistantSession(sessionId: string): Promise<void> {
  await api.delete(`/assistant/sessions/${sessionId}`);
}

export async function getAssistantMessages(sessionId: string) {
  const response = await api.get<any[]>(`/assistant/sessions/${sessionId}/messages`);
  return response.map(assistantMessageApiToViewModel);
}

export async function postAssistantMessage(
  sessionId: string,
  payload: AssistantPayload,
): Promise<AssistantSessionMessageResult> {
  const response = await api.post<any>(`/assistant/sessions/${sessionId}/messages`, {
    text: payload.text,
    preferredMode: payload.preferredMode ?? "deterministic",
    context: payload.context,
  });
  return assistantSessionMessageResultApiToViewModel(response);
}

export async function streamAssistantMessage(
  sessionId: string,
  payload: AssistantPayload,
  options: {
    onEvent?: (event: AssistantStreamEvent) => void;
    signal?: AbortSignal;
  } = {},
): Promise<AssistantSessionMessageResult> {
  let finalResult: AssistantSessionMessageResult | null = null;
  let streamError: { code: string; message: string } | null = null;
  await api.stream<any>(`/assistant/sessions/${sessionId}/messages/stream`, {
    body: {
      text: payload.text,
      preferredMode: payload.preferredMode ?? "deterministic",
      context: payload.context,
    },
    signal: options.signal,
    onEvent: (event) => {
      const normalized = assistantStreamEventApiToViewModel(event);
      if (normalized.type === "done") {
        finalResult = normalized.result;
      }
      if (normalized.type === "error") {
        streamError = { code: normalized.code, message: normalized.message };
      }
      options.onEvent?.(normalized);
    },
  });
  if (streamError) {
    throw new Error(streamError.message);
  }
  if (!finalResult) {
    throw new Error("Поток ответа завершился без финального результата");
  }
  return finalResult;
}

export async function getAssistantCapabilities(): Promise<AssistantCapabilities> {
  const response = await api.get<any>("/assistant/capabilities");
  return assistantCapabilitiesApiToViewModel(response);
}

export async function getAssistantPromptSuggestions(): Promise<AssistantPromptSuggestion[]> {
  const response = await api.get<any>("/assistant/prompts/suggestions");
  return assistantPromptSuggestionsApiToViewModel(response);
}

export async function getAssistantContextOptions(): Promise<AssistantContextOptions> {
  const response = await api.get<any>("/assistant/context-options");
  return assistantContextOptionsApiToViewModel(response);
}
