import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query/keys";
import { getInboundTimeline, syncInboundSheet } from "@/services/inbound.service";

export function useInboundTimelineQuery() {
  return useQuery({
    queryKey: queryKeys.inbound.timeline(),
    queryFn: getInboundTimeline,
  });
}

export function useInboundSyncMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: syncInboundSheet,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.inbound.all });
      await queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
      await queryClient.invalidateQueries({ queryKey: queryKeys.stock.all });
    },
  });
}
