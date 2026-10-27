import { useConfig } from "../config/useConfig";
import { useAuthenticatedQuery } from "./useAuthenticatedQuery";
import { getResourceDetail } from "../queries/api";

export function mergeSourceDetailsKey(endpoint, resourceIds) {
  return [endpoint, "merge-source-details", ...(resourceIds ?? [])];
}

export function useMergeSourceDetails(endpoint, resourceIds, enabled = true) {
  const config = useConfig();
  const ids = resourceIds ?? [];

  return useAuthenticatedQuery({
    queryKey: mergeSourceDetailsKey(endpoint, ids),
    queryFn: (fetcher) =>
      Promise.all(
        ids.map((id) => getResourceDetail(config, id, fetcher, endpoint)),
      ),
    enabled: enabled && ids.length > 0,
  });
}
