import { useConfig } from "../config/useConfig";
import { useAuthenticatedQuery } from "./useAuthenticatedQuery";
import { getResourceDetail } from "../queries/api";

export function mergedResourceDetailKey(endpoint, resourceId) {
  return [endpoint, "merged-resource-detail", resourceId];
}

export function useMergedResourceDetail(endpoint, resourceId) {
  const config = useConfig();

  return useAuthenticatedQuery({
    queryKey: mergedResourceDetailKey(endpoint, resourceId),
    queryFn: (fetcher) =>
      getResourceDetail(config, resourceId, fetcher, endpoint),
    enabled: Boolean(resourceId),
  });
}
