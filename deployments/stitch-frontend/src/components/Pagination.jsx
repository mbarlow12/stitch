import { PAGE_SIZE_OPTIONS } from "../queries/resources";

const WIDE_WINDOW_MAX_PAGES = 9999;
const WIDE_WINDOW = 3;
const NARROW_WINDOW = 1;

function getSlots(currentPage, totalPages, windowSize) {
  const slot = (page, visible = true) => ({ page, visible, ellipsis: false });
  const ellipsis = (visible = true) => ({
    page: null,
    visible,
    ellipsis: true,
  });

  const edgeRun = windowSize + 2;
  const run = (startPage) =>
    Array.from({ length: edgeRun }, (_, i) => {
      const page = startPage + i;
      return slot(page, page >= 1 && page <= totalPages);
    });

  if (currentPage < edgeRun) {
    return [
      ...run(1),
      ellipsis(totalPages > edgeRun + 1),
      slot(totalPages, totalPages > edgeRun),
    ];
  }

  if (currentPage > totalPages - edgeRun + 1) {
    return [
      slot(1, totalPages > edgeRun),
      ellipsis(totalPages > edgeRun + 1),
      ...run(totalPages - edgeRun + 1),
    ];
  }

  const half = (windowSize - 1) / 2;
  return [
    slot(1),
    ellipsis(),
    ...Array.from({ length: windowSize }, (_, i) =>
      slot(currentPage - half + i),
    ),
    ellipsis(),
    slot(totalPages),
  ];
}

const buttonBase =
  "flex h-9 shrink-0 items-center justify-center rounded-md border text-sm font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:ring-offset-2";

const navButtonBase = `${buttonBase} w-9`;

const pageButtonBase = `${buttonBase} min-w-9 px-2 tabular-nums`;

export default function Pagination({
  page,
  pageSize,
  totalCount,
  totalPages,
  onPageChange,
  onPageSizeChange,
}) {
  const slots = getSlots(
    page,
    totalPages,
    totalPages > WIDE_WINDOW_MAX_PAGES ? NARROW_WINDOW : WIDE_WINDOW,
  );
  const firstItem = (page - 1) * pageSize + 1;
  const lastItem = Math.min(page * pageSize, totalCount);

  return (
    <div className="mt-4 flex flex-wrap items-center justify-between gap-y-3 text-sm text-ink-muted">
      <span className="font-medium">
        Showing {firstItem.toLocaleString()}–{lastItem.toLocaleString()} of{" "}
        {totalCount.toLocaleString()}
      </span>

      {totalPages > 1 && (
        <div className="flex flex-wrap items-center gap-1">
          <button
            onClick={() => onPageChange(page - 1)}
            disabled={page === 1}
            className={`${navButtonBase} border-line bg-panel text-ink hover:bg-surface disabled:cursor-not-allowed disabled:opacity-40`}
            aria-label="Previous page"
          >
            ‹
          </button>

          {slots.map((slot, i) =>
            slot.ellipsis ? (
              <span
                key={`ellipsis-${i}`}
                style={{ visibility: slot.visible ? "visible" : "hidden" }}
                className="flex h-9 w-9 shrink-0 items-center justify-center text-ink-muted select-none"
                aria-hidden="true"
              >
                …
              </span>
            ) : (
              <button
                key={`slot-${i}`}
                onClick={() => slot.visible && onPageChange(slot.page)}
                aria-current={slot.page === page ? "page" : undefined}
                style={{ visibility: slot.visible ? "visible" : "hidden" }}
                tabIndex={slot.visible ? 0 : -1}
                className={`${pageButtonBase} ${
                  slot.page === page
                    ? "border-primary bg-primary text-white"
                    : "border-line bg-panel text-ink hover:bg-surface"
                }`}
              >
                {slot.page.toLocaleString()}
              </button>
            ),
          )}

          <button
            onClick={() => onPageChange(page + 1)}
            disabled={page === totalPages}
            className={`${navButtonBase} border-line bg-panel text-ink hover:bg-surface disabled:cursor-not-allowed disabled:opacity-40`}
            aria-label="Next page"
          >
            ›
          </button>
        </div>
      )}

      <div className="flex items-center gap-2">
        <label
          htmlFor="page-size-select"
          className="font-medium text-ink-muted"
        >
          Per page:
        </label>
        <select
          id="page-size-select"
          value={pageSize}
          onChange={(e) => onPageSizeChange(Number(e.target.value))}
          className="rounded-md border border-line bg-panel px-2 py-1 text-sm text-ink focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
        >
          {PAGE_SIZE_OPTIONS.map((size) => (
            <option key={size} value={size}>
              {size}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
