import { PAGE_SIZE_OPTIONS } from "../queries/resources";

export const PAGE_SIZE_STORAGE_KEY = "stitch.resources.pageSize";

export function getRememberedPageSize() {
  let stored;
  try {
    stored = window.sessionStorage.getItem(PAGE_SIZE_STORAGE_KEY);
  } catch {
    return null;
  }
  const value = Number(stored);
  return stored && PAGE_SIZE_OPTIONS.includes(value) ? value : null;
}

export function rememberPageSize(pageSize) {
  if (!PAGE_SIZE_OPTIONS.includes(pageSize)) return;
  try {
    window.sessionStorage.setItem(PAGE_SIZE_STORAGE_KEY, String(pageSize));
  } catch {
    return;
  }
}
