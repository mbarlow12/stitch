import { useQueries } from "@tanstack/react-query";
import { mergeSourceDetailsKey } from "./useMergeSourceDetails";
import { mergedResourceDetailKey } from "./useMergedResourceDetail";
import { candidateDisplayName } from "../utils/mergeCandidateName";

export function useCandidateDisplayNames(endpoint, candidates) {
  const list = candidates ?? [];
  const queries = list.flatMap((candidate) => [
    {
      queryKey: mergeSourceDetailsKey(endpoint, candidate.resource_ids),
      enabled: false,
    },
    ...(candidate.merged_resource_id
      ? [
          {
            queryKey: mergedResourceDetailKey(
              endpoint,
              candidate.merged_resource_id,
            ),
            enabled: false,
          },
        ]
      : []),
  ]);

  return useQueries({
    queries,
    combine: (results) => {
      const namesById = new Map();
      let index = 0;
      for (const candidate of list) {
        const source = results[index++];
        const merged = candidate.merged_resource_id ? results[index++] : null;
        const settled =
          source.status !== "pending" &&
          (!merged || merged.status !== "pending");
        if (settled) {
          namesById.set(
            candidate.id,
            candidateDisplayName(candidate.id, {
              sourceDetails: source.data,
              mergedResource: merged?.data,
            }),
          );
        }
      }
      return { namesById, loadedCount: namesById.size, total: list.length };
    },
  });
}
