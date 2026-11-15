import { FILTER_FIELDS } from "./filters";
import { SORTABLE_COLUMN_KEYS } from "./listColumns";
import {
  DEFAULT_PAGE,
  DEFAULT_PAGE_SIZE,
  PAGE_SIZE_OPTIONS,
} from "../queries/resources";

const FILTER_KEYS = FILTER_FIELDS.map((field) => field.key);
const SORT_ORDERS = ["asc", "desc"];
const DEFAULT_SORT_ORDER = "asc";

function parsePage(raw) {
  const value = Number(raw);
  return /^\d+$/.test(raw ?? "") && Number.isSafeInteger(value) && value >= 1
    ? value
    : DEFAULT_PAGE;
}

function parsePageSize(raw, fallbackPageSize) {
  const value = Number(raw);
  return PAGE_SIZE_OPTIONS.includes(value) ? value : fallbackPageSize;
}

function parseSort(rawSortBy, rawSortOrder) {
  if (!SORTABLE_COLUMN_KEYS.includes(rawSortBy)) {
    return { sortBy: null, sortOrder: DEFAULT_SORT_ORDER };
  }
  return {
    sortBy: rawSortBy,
    sortOrder: SORT_ORDERS.includes(rawSortOrder)
      ? rawSortOrder
      : DEFAULT_SORT_ORDER,
  };
}

export function parseListParams(
  searchParams,
  { fallbackPageSize = DEFAULT_PAGE_SIZE } = {},
) {
  const filters = {};
  for (const key of FILTER_KEYS) {
    filters[key] = searchParams.getAll(key).filter((value) => value !== "");
  }

  return {
    page: parsePage(searchParams.get("page")),
    pageSize: parsePageSize(searchParams.get("page_size"), fallbackPageSize),
    q: (searchParams.get("q") ?? "").trim(),
    ...parseSort(searchParams.get("sort_by"), searchParams.get("sort_order")),
    filters,
  };
}

export function toListParams(
  { page, pageSize, q, sortBy, sortOrder, filters },
  { fallbackPageSize = DEFAULT_PAGE_SIZE } = {},
) {
  const params = new URLSearchParams();
  const trimmedSearch = (q ?? "").trim();
  const hasFilters = FILTER_KEYS.some((key) =>
    (filters?.[key] ?? []).some((value) => value !== ""),
  );
  const hasOtherState =
    page > DEFAULT_PAGE ||
    Boolean(trimmedSearch) ||
    Boolean(sortBy) ||
    hasFilters;

  if (page > DEFAULT_PAGE) params.set("page", String(page));
  if (
    pageSize &&
    (hasOtherState ||
      pageSize !== DEFAULT_PAGE_SIZE ||
      pageSize !== fallbackPageSize)
  ) {
    params.set("page_size", String(pageSize));
  }

  if (trimmedSearch) params.set("q", trimmedSearch);

  if (sortBy) {
    params.set("sort_by", sortBy);
    params.set("sort_order", sortOrder ?? DEFAULT_SORT_ORDER);
  }

  for (const key of FILTER_KEYS) {
    for (const value of filters?.[key] ?? []) {
      if (value !== "") params.append(key, value);
    }
  }

  return params;
}
