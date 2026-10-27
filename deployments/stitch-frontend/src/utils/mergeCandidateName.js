import { SOURCE_PRIORITY } from "../constants/sourceMeta";
import { isEmptyValue } from "./mergeComparison";

function sourceRank(source) {
  const index = SOURCE_PRIORITY.indexOf(source);
  return index === -1 ? SOURCE_PRIORITY.length : index;
}

export function pickCandidateName(details) {
  let winner = null;

  for (const detail of details) {
    const name = detail?.data?.name;
    if (isEmptyValue(name)) continue;

    const rank = sourceRank(detail?.provenance?.name);
    if (!winner || rank < winner.rank) {
      winner = { name, rank };
    }
  }

  return winner?.name ?? null;
}

export function candidateDisplayName(
  candidateId,
  { sourceDetails, mergedResource },
) {
  const mergedName = isEmptyValue(mergedResource?.data?.name)
    ? null
    : mergedResource.data.name;
  const sourceName = sourceDetails ? pickCandidateName(sourceDetails) : null;
  return mergedName ?? sourceName ?? `Candidate #${candidateId}`;
}
