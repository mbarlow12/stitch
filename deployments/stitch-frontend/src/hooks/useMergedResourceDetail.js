import { useConfig } from "../config/useConfig";
import { useAuthenticatedQuery } from "./useAuthenticatedQuery";
import { getResourceDetail } from "../queries/api";

export function useMergedResourceDetail(endpoint, resourceId) {
  const config = useConfig();

  return useAuthenticatedQuery({
    queryKey: [endpoint, "merged-resource-detail", resourceId],
    queryFn: (fetcher) =>
      getResourceDetail(config, resourceId, fetcher, endpoint),
    enabled: Boolean(resourceId),
  });
}
