import { useMutation, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query/keys";
import {
  askAssistant,
  createAssistantSession,
  deleteAssistantSession,
  postAssistantMessage,
  updateAssistantSession,
  type AssistantPayload,
  type CreateAssistantSessionPayload,
  type UpdateAssistantSessionPayload,
} from "@/services/assistant.service";

export function useAssistantMutation() {
  return useMutation({
    mutationFn: askAssistant,
  });
}

export function useCreateAssistantSessionMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateAssistantSessionPayload) => createAssistantSession(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.assistant.sessions() });
    },
  });
}

export function useAssistantMessageMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      sessionId,
      payload,
    }: {
      sessionId: string;
      payload: AssistantPayload;
    }) => postAssistantMessage(sessionId, payload),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.assistant.sessions() });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.assistant.messages(result.session.id),
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.assistant.session(result.session.id),
      });
    },
  });
}

export function useUpdateAssistantSessionMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      sessionId,
      payload,
    }: {
      sessionId: string;
      payload: UpdateAssistantSessionPayload;
    }) => updateAssistantSession(sessionId, payload),
    onSuccess: (session) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.assistant.sessions() });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.assistant.session(session.id),
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.assistant.messages(session.id),
      });
    },
  });
}

export function useDeleteAssistantSessionMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: string) => deleteAssistantSession(sessionId),
    onSuccess: (_result, sessionId) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.assistant.sessions() });
      void queryClient.removeQueries({ queryKey: queryKeys.assistant.session(sessionId) });
      void queryClient.removeQueries({ queryKey: queryKeys.assistant.messages(sessionId) });
    },
  });
}
