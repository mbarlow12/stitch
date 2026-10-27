export const MERGE_REVIEW_SORT_OPTIONS = [
  { value: "newest", label: "Newest first" },
  { value: "oldest", label: "Oldest first" },
  { value: "name-asc", label: "Name A–Z" },
  { value: "name-desc", label: "Name Z–A" },
  { value: "status", label: "Status" },
];

export const DEFAULT_MERGE_REVIEW_SORT = "newest";

export const MERGE_REVIEW_SORT_STORAGE_KEY = "stitch.mergeReview.sort";

const SORT_VALUES = MERGE_REVIEW_SORT_OPTIONS.map((option) => option.value);

export function getRememberedMergeReviewSort() {
  let stored;
  try {
    stored = window.sessionStorage.getItem(MERGE_REVIEW_SORT_STORAGE_KEY);
  } catch {
    return DEFAULT_MERGE_REVIEW_SORT;
  }
  return SORT_VALUES.includes(stored) ? stored : DEFAULT_MERGE_REVIEW_SORT;
}

export function rememberMergeReviewSort(sort) {
  if (!SORT_VALUES.includes(sort)) return;
  try {
    window.sessionStorage.setItem(MERGE_REVIEW_SORT_STORAGE_KEY, sort);
  } catch {
    return;
  }
}
