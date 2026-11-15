import { DEFAULT_PAGE, PAGE_SIZE_OPTIONS } from "../queries/resources";

export const MERGE_STATUSES = ["PENDING", "APPROVED", "DENIED"];
export const DEFAULT_STATUSES = ["PENDING"];
const ALL_STATUSES = "all";

export const DEFAULT_QUEUE_PAGE_SIZE = 25;

export const QUEUE_SORT_OPTIONS = [
  {
    key: "newest",
    label: "Newest first",
    sortBy: "created",
    sortOrder: "desc",
  },
  { key: "oldest", label: "Oldest first", sortBy: "created", sortOrder: "asc" },
  { key: "name-asc", label: "Name A–Z", sortBy: "name", sortOrder: "asc" },
  { key: "name-desc", label: "Name Z–A", sortBy: "name", sortOrder: "desc" },
  { key: "status", label: "Status", sortBy: "status", sortOrder: "asc" },
  {
    key: "recently-reviewed",
    label: "Recently reviewed",
    sortBy: "reviewed_at",
    sortOrder: "desc",
  },
  {
    key: "earliest-reviewed",
    label: "Earliest reviewed",
    sortBy: "reviewed_at",
    sortOrder: "asc",
  },
];
const DEFAULT_SORT = QUEUE_SORT_OPTIONS[0];

function parsePage(raw) {
  const value = Number(raw);
  return /^\d+$/.test(raw ?? "") && Number.isSafeInteger(value) && value >= 1
    ? value
    : DEFAULT_PAGE;
}

function parsePageSize(raw) {
  const value = Number(raw);
  return PAGE_SIZE_OPTIONS.includes(value) ? value : DEFAULT_QUEUE_PAGE_SIZE;
}

function parseStatuses(rawValues) {
  if (rawValues.includes(ALL_STATUSES)) return [];
  const statuses = MERGE_STATUSES.filter((status) =>
    rawValues.includes(status),
  );
  return statuses.length ? statuses : DEFAULT_STATUSES;
}

function parseSort(rawSortBy, rawSortOrder) {
  return (
    QUEUE_SORT_OPTIONS.find(
      (option) =>
        option.sortBy === rawSortBy && option.sortOrder === rawSortOrder,
    ) ?? DEFAULT_SORT
  );
}

function isDefaultStatuses(statuses) {
  return (
    statuses.length === DEFAULT_STATUSES.length &&
    DEFAULT_STATUSES.every((status) => statuses.includes(status))
  );
}

export function parseMergeReviewParams(searchParams) {
  return {
    page: parsePage(searchParams.get("page")),
    pageSize: parsePageSize(searchParams.get("page_size")),
    q: (searchParams.get("q") ?? "").trim(),
    statuses: parseStatuses(searchParams.getAll("status")),
    sortKey: parseSort(
      searchParams.get("sort_by"),
      searchParams.get("sort_order"),
    ).key,
  };
}

export function toMergeReviewParams({ page, pageSize, q, statuses, sortKey }) {
  const params = new URLSearchParams();
  if (page > DEFAULT_PAGE) params.set("page", String(page));
  if (pageSize !== DEFAULT_QUEUE_PAGE_SIZE) {
    params.set("page_size", String(pageSize));
  }

  const trimmedSearch = (q ?? "").trim();
  if (trimmedSearch) params.set("q", trimmedSearch);

  if (statuses.length === 0) {
    params.set("status", ALL_STATUSES);
  } else if (!isDefaultStatuses(statuses)) {
    for (const status of MERGE_STATUSES) {
      if (statuses.includes(status)) params.append("status", status);
    }
  }

  const sort = QUEUE_SORT_OPTIONS.find((option) => option.key === sortKey);
  if (sort && sort !== DEFAULT_SORT) {
    params.set("sort_by", sort.sortBy);
    params.set("sort_order", sort.sortOrder);
  }

  return params;
}

export function toMergeCandidateQuery({
  page,
  pageSize,
  q,
  statuses,
  sortKey,
}) {
  const sort =
    QUEUE_SORT_OPTIONS.find((option) => option.key === sortKey) ?? DEFAULT_SORT;
  return {
    page,
    page_size: pageSize,
    q: q || undefined,
    status: statuses.length ? statuses : undefined,
    sort_by: sort.sortBy,
    sort_order: sort.sortOrder,
  };
}
