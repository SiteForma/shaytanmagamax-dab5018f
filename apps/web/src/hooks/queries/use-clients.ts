import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query/keys";
import {
  getClientCategoryExposure,
  getClientDetail,
  getClientReserve,
  getClientTopSkus,
  listClients,
} from "@/services/client.service";

export function useClientsQuery() {
  return useQuery({
    queryKey: queryKeys.clients.list(),
    queryFn: listClients,
  });
}

export function useClientDetailQuery(clientId: string | null) {
  return useQuery({
    queryKey: queryKeys.clients.detail(clientId),
    queryFn: () => getClientDetail(clientId as string),
    enabled: Boolean(clientId),
  });
}

export function useClientReserveRowsQuery(clientId: string | null) {
  return useQuery({
    queryKey: queryKeys.clients.reserveRows(clientId),
    queryFn: () => getClientReserve(clientId as string),
    enabled: Boolean(clientId),
  });
}

export function useClientTopSkusQuery(clientId: string | null) {
  return useQuery({
    queryKey: queryKeys.clients.topSkus(clientId),
    queryFn: () => getClientTopSkus(clientId as string),
    enabled: Boolean(clientId),
  });
}

export function useClientCategoryExposureQuery(clientId: string | null) {
  return useQuery({
    queryKey: queryKeys.clients.categoryExposure(clientId),
    queryFn: () => getClientCategoryExposure(clientId as string),
    enabled: Boolean(clientId),
  });
}
