import { useMutation, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query/keys";
import { calculateReserve } from "@/services/reserve.service";
import type { ReserveCalculationRequest } from "@/types";

export function useReserveCalculationMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ReserveCalculationRequest) => calculateReserve(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.reserve.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.clients.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.stock.all });
    },
  });
}
