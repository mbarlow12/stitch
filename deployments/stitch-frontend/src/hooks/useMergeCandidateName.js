import { useMergeSourceDetails } from "./useMergeSourceDetails";
import { pickCandidateName } from "../utils/mergeCandidateName";

export function useMergeCandidateName(endpoint, resourceIds) {
  const { data: details } = useMergeSourceDetails(endpoint, resourceIds);

  return details ? pickCandidateName(details) : null;
}
