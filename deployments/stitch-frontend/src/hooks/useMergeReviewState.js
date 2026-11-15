import { useMemo } from "react";
import { useSearchParams } from "react-router";
import {
  parseMergeReviewParams,
  toMergeReviewParams,
} from "../config/mergeReviewParams";
import { DEFAULT_PAGE } from "../queries/resources";

export function useMergeReviewState() {
  const [searchParams, setSearchParams] = useSearchParams();
  const state = parseMergeReviewParams(searchParams);

  const setters = useMemo(() => {
    function write(changes, { replace }) {
      setSearchParams(
        (current) =>
          toMergeReviewParams({
            ...parseMergeReviewParams(current),
            ...changes,
          }),
        { replace },
      );
    }

    return {
      setPage: (page, { replace = false } = {}) => write({ page }, { replace }),
      setPageSize: (pageSize) =>
        write({ pageSize, page: DEFAULT_PAGE }, { replace: false }),
      setStatuses: (statuses) =>
        write({ statuses, page: DEFAULT_PAGE }, { replace: true }),
      setSortKey: (sortKey) =>
        write({ sortKey, page: DEFAULT_PAGE }, { replace: true }),
      setSearch: (q) => write({ q, page: DEFAULT_PAGE }, { replace: true }),
    };
  }, [setSearchParams]);

  return { ...state, ...setters };
}
