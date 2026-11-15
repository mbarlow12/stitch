import { useSearchParams } from "react-router";
import { parseListParams, toListParams } from "../config/listParams";
import {
  getRememberedPageSize,
  rememberPageSize,
} from "../config/pageSizePreference";
import { DEFAULT_PAGE, DEFAULT_PAGE_SIZE } from "../queries/resources";

export function useListState() {
  const [searchParams, setSearchParams] = useSearchParams();
  const fallbackPageSize = getRememberedPageSize() ?? DEFAULT_PAGE_SIZE;
  const state = parseListParams(searchParams, { fallbackPageSize });

  function write(changes, { replace }, options = { fallbackPageSize }) {
    setSearchParams(toListParams({ ...state, ...changes }, options), {
      replace,
    });
  }

  return {
    page: state.page,
    pageSize: state.pageSize,
    q: state.q,
    filters: state.filters,
    sort: { column: state.sortBy, direction: state.sortOrder },

    setPage: (page) => write({ page }, { replace: false }),
    setPageSize: (pageSize) => {
      rememberPageSize(pageSize);
      write(
        { pageSize, page: DEFAULT_PAGE },
        { replace: false },
        { fallbackPageSize: getRememberedPageSize() ?? DEFAULT_PAGE_SIZE },
      );
    },
    setSearch: (q) => write({ q, page: DEFAULT_PAGE }, { replace: true }),
    setSort: ({ column, direction }) =>
      write(
        { sortBy: column, sortOrder: direction, page: DEFAULT_PAGE },
        { replace: true },
      ),
    setFilters: (filters) =>
      write({ filters, page: DEFAULT_PAGE }, { replace: true }),
  };
}
