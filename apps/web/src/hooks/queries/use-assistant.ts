import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query/keys";
import {
  getAssistantCapabilities,
  getAssistantContextOptions,
  getAssistantMessages,
  getAssistantPromptSuggestions,
  getAssistantSession,
  listAssistantSessions,
} from "@/services/assistant.service";

export function useAssistantSessionsQuery() {
  return useQuery({
    queryKey: queryKeys.assistant.sessions(),
    queryFn: listAssistantSessions,
  });
}

export function useAssistantSessionQuery(sessionId: string | null) {
  return useQuery({
    queryKey: queryKeys.assistant.session(sessionId),
    queryFn: () => getAssistantSession(sessionId as string),
    enabled: Boolean(sessionId),
  });
}

export function useAssistantMessagesQuery(sessionId: string | null) {
  return useQuery({
    queryKey: queryKeys.assistant.messages(sessionId),
    queryFn: () => getAssistantMessages(sessionId as string),
    enabled: Boolean(sessionId),
  });
}

export function useAssistantCapabilitiesQuery() {
  return useQuery({
    queryKey: queryKeys.assistant.capabilities(),
    queryFn: getAssistantCapabilities,
  });
}

export function useAssistantPromptSuggestionsQuery() {
  return useQuery({
    queryKey: queryKeys.assistant.suggestions(),
    queryFn: getAssistantPromptSuggestions,
  });
}

export function useAssistantContextOptionsQuery() {
  return useQuery({
    queryKey: queryKeys.assistant.contextOptions(),
    queryFn: getAssistantContextOptions,
  });
}
