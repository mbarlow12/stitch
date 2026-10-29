import { keepPreviousData, queryOptions } from "@tanstack/react-query";
import {
  getResourceFilterOptions,
  getResource,
  getResources,
  getResourceDetail,
  getFieldSourceValues,
  getMergeCandidates,
  getMergeCandidate,
} from "./api";

export const DEFAULT_STALE_TIME = 60_000;
export const DEFAULT_PAGE = 1;
export const DEFAULT_PAGE_SIZE = 10;
export const PAGE_SIZE_OPTIONS = [10, 25, 50, 100];

const keys = {
  all: (endpoint = "resources") => [endpoint],
  lists: (endpoint = "resources") => [...keys.all(endpoint), "list"],
  list: (endpoint = "resources", filters) => [...keys.lists(endpoint), filters],
  filterOptions: (endpoint = "resources", params) => [
    ...keys.all(endpoint),
    "filter-options",
    params,
  ],
  details: (endpoint = "resources") => [...keys.all(endpoint), "detail"],
  detail: (endpoint = "resources", id) => [...keys.details(endpoint), id],
  fieldSources: (endpoint = "oil-gas-fields", id, field) => [
    ...keys.detail(endpoint, id),
    "field-sources",
    field,
  ],
  views: (endpoint = "resources") => [...keys.all(endpoint), "view"],
  view: (endpoint = "resources", id) => [...keys.views(endpoint), id],
  mergeCandidates: (endpoint = "oil-gas-fields") => [
    ...keys.all(endpoint),
    "merge-candidates",
  ],
  mergeCandidate: (endpoint = "oil-gas-fields", id) => [
    ...keys.mergeCandidates(endpoint),
    id,
  ],
};

export const resourceQueries = {
  list: (
    config,
    endpoint = "resources",
    page = DEFAULT_PAGE,
    page_size = DEFAULT_PAGE_SIZE,
    filters = {},
    q,
    sort_by,
    sort_order,
  ) =>
    queryOptions({
      queryKey: keys.list(endpoint, {
        page,
        page_size,
        ...filters,
        q,
        sort_by,
        sort_order,
      }),
      queryFn: (fetcher) =>
        getResources(config, fetcher, endpoint, {
          page,
          page_size,
          filters,
          q,
          sort_by,
          sort_order,
        }),
      staleTime: DEFAULT_STALE_TIME,
      placeholderData: keepPreviousData,
    }),

  filterOptions: (config, endpoint = "resources", filters = {}, q) =>
    queryOptions({
      queryKey: keys.filterOptions(endpoint, {
        ...Object.fromEntries(
          Object.entries(filters).filter(([, values]) => values.length > 0),
        ),
        q,
      }),
      queryFn: (fetcher) =>
        getResourceFilterOptions(config, fetcher, endpoint, { filters, q }),
      staleTime: DEFAULT_STALE_TIME,
    }),

  detail: (config, endpoint = "resources", id) =>
    queryOptions({
      queryKey: keys.detail(endpoint, id),
      queryFn: (fetcher) => getResourceDetail(config, id, fetcher, endpoint),
    }),

  fieldSources: (config, endpoint = "oil-gas-fields", id, field) =>
    queryOptions({
      queryKey: keys.fieldSources(endpoint, id, field),
      queryFn: (fetcher) =>
        getFieldSourceValues(config, id, field, fetcher, endpoint),
      staleTime: DEFAULT_STALE_TIME,
    }),

  view: (config, endpoint = "resources", id) =>
    queryOptions({
      queryKey: keys.view(endpoint, id),
      queryFn: (fetcher) => getResource(config, id, fetcher, endpoint),
    }),

  mergeCandidates: (config, endpoint = "oil-gas-fields") =>
    queryOptions({
      queryKey: keys.mergeCandidates(endpoint),
      queryFn: (fetcher) => getMergeCandidates(config, fetcher, endpoint),
    }),

  mergeCandidate: (config, endpoint = "oil-gas-fields", id) =>
    queryOptions({
      queryKey: keys.mergeCandidate(endpoint, id),
      queryFn: (fetcher) => getMergeCandidate(config, id, fetcher, endpoint),
    }),
};
