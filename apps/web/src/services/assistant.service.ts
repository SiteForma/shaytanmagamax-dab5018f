import type {
  AssistantCapabilities,
  AssistantContextOptions,
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
