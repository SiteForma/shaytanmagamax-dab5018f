import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query/keys";
import { getInboundTimeline } from "@/services/inbound.service";

export function useInboundTimelineQuery() {
  return useQuery({
    queryKey: queryKeys.inbound.timeline(),
    queryFn: getInboundTimeline,
  });
}
