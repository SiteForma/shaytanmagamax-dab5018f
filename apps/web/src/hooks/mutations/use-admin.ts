import { useMutation, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query/keys";
import { retryAdminJob, updateAdminUserRole } from "@/services/admin.service";

function invalidateAdmin(queryClient: ReturnType<typeof useQueryClient>) {
  void queryClient.invalidateQueries({ queryKey: queryKeys.admin.all });
  void queryClient.invalidateQueries({ queryKey: queryKeys.exports.all });
  void queryClient.invalidateQueries({ queryKey: queryKeys.uploads.all });
}

export function useUpdateAdminUserRoleMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) =>
      updateAdminUserRole(userId, role),
    onSuccess: () => invalidateAdmin(queryClient),
  });
}

export function useRetryAdminJobMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: retryAdminJob,
    onSuccess: () => invalidateAdmin(queryClient),
  });
}
