import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getCurrentUser, getCurrentSession, login, logout } from "@/services/auth.service";
import { DEV_USER_ID } from "@/lib/auth/config";
import { hasCapability, type Capability } from "@/lib/access";
import { queryKeys } from "@/lib/query/keys";

export function useCurrentUserQuery() {
  return useQuery({
    queryKey: queryKeys.auth.currentUser(),
    queryFn: getCurrentUser,
    enabled: Boolean(getCurrentSession() || DEV_USER_ID),
  });
}

export function useCapabilities() {
  const { data } = useCurrentUserQuery();
  return data?.capabilities ?? [];
}

export function useHasCapability(capability: Capability) {
  const { data } = useCurrentUserQuery();
  return hasCapability(data, capability);
}

export function useLoginMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: login,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.auth.all });
    },
  });
}

export function useLogoutAction() {
  const queryClient = useQueryClient();
  return () => {
    logout();
    void queryClient.invalidateQueries({ queryKey: queryKeys.auth.all });
  };
}
