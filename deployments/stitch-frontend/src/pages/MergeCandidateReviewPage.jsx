import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import Button from "../components/Button";
import FilterDropdown from "../components/FilterDropdown";
import Input from "../components/Input";
import MergeSourceComparison from "../components/MergeSourceComparison";
import MergedResourceView from "../components/MergedResourceView";
import Pagination from "../components/Pagination";
import Select from "../components/Select";
import {
  MERGE_STATUSES,
  QUEUE_SORT_OPTIONS,
  toMergeCandidateQuery,
} from "../config/mergeReviewParams";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useMergeReviewState } from "../hooks/useMergeReviewState";
import { useMergeSourceDetails } from "../hooks/useMergeSourceDetails";
import {
  useMergeCandidates,
  useMergeCandidate,
  useReviewMergeCandidate,
} from "../hooks/useResources";

const ENDPOINT = "oil-gas-fields";
const TWO_COLUMN_LAYOUT_QUERY = "(min-width: 48rem)";
const STATUS_FILTER_LABELS = {
  PENDING: "Pending",
  APPROVED: "Approved",
  DENIED: "Denied",
};

function getStatusClasses(status) {
  if (status === "PENDING") {
    return "border-warning/30 bg-warning-soft text-warning";
  }
  if (status === "APPROVED") {
    return "border-success/25 bg-success-soft text-success-strong";
  }
  if (status === "DENIED") {
    return "border-danger/25 bg-danger-soft text-danger";
  }
  return "border-line bg-surface text-ink";
}

function getStatusLabel(status) {
  return status === "PENDING" ? "CANDIDATE" : status;
}

function StatusBadge({ status }) {
  return (
    <span
      className={`shrink-0 rounded-full border px-2 py-0.5 text-xs font-semibold ${getStatusClasses(status)}`}
    >
      {getStatusLabel(status)}
    </span>
  );
}

function candidateSourcesTitle(candidate) {
  const parts = [`Source resources: ${candidate.resource_ids.join(", ")}`];
  if (candidate.merged_resource_id) {
    parts.push(`Merged resource: ${candidate.merged_resource_id}`);
  }
  return parts.join(" · ");
}

function candidateDisplayName(candidate) {
  return candidate.name ?? `Candidate #${candidate.id}`;
}

function CandidateQueueItem({ candidate, isSelected, onSelect }) {
  const displayName = candidateDisplayName(candidate);

  return (
    <button
      type="button"
      onClick={() => onSelect(candidate.id)}
      aria-pressed={isSelected}
      title={candidateSourcesTitle(candidate)}
      className={`w-full rounded-md border px-3 py-3 text-left transition ${
        isSelected
          ? "border-primary bg-primary-soft"
          : "border-transparent bg-panel hover:border-line hover:bg-surface"
      } focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:ring-offset-2`}
    >
      <span className="flex items-start justify-between gap-2">
        <span className="min-w-0 break-words font-semibold text-ink">
          {displayName}
        </span>
        <StatusBadge status={candidate.status} />
      </span>
    </button>
  );
}

function QueueSearch({ q, onSearch }) {
  const [searchText, setSearchText] = useState(q);
  const [lastQ, setLastQ] = useState(q);
  if (q !== lastQ) {
    setLastQ(q);
    setSearchText(q);
  }

  function handleChange(event) {
    const newValue = event.target.value;
    setSearchText(newValue);
    if (newValue === "" && q !== "") onSearch("");
  }

  function handleSubmit(event) {
    event.preventDefault();
    const normalizedSearch = searchText.trim();
    setSearchText(normalizedSearch);
    onSearch(normalizedSearch);
  }

  function handleClear() {
    setSearchText("");
    onSearch("");
  }

  return (
    <form onSubmit={handleSubmit} role="search" className="flex w-full gap-2">
      <div className="relative min-w-0 flex-1">
        <Input
          type="search"
          value={searchText}
          onChange={handleChange}
          placeholder="Name, basin or ID"
          aria-label="Search candidates"
          className="w-full pr-9"
        />
        {searchText && (
          <button
            type="button"
            onClick={handleClear}
            aria-label="Clear search"
            className="absolute right-1.5 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md text-base leading-none text-ink-muted transition-colors hover:bg-rmiblue-100 hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-energy/60"
          >
            <span aria-hidden="true">×</span>
          </button>
        )}
      </div>
      <Button type="submit" variant="secondary">
        Search
      </Button>
    </form>
  );
}

function QueueControls({
  statuses,
  onStatusesChange,
  sortKey,
  onSortKeyChange,
}) {
  const statusOptions = MERGE_STATUSES.map((status) => ({
    value: status,
    label: STATUS_FILTER_LABELS[status],
  }));

  return (
    <div className="flex flex-wrap items-center gap-2">
      <FilterDropdown
        label="Status"
        options={statusOptions}
        selected={statuses}
        onChange={onStatusesChange}
      />
      <label className="sr-only" htmlFor="queue-sort">
        Sort candidates
      </label>
      <Select
        id="queue-sort"
        value={sortKey}
        onChange={(event) => onSortKeyChange(event.target.value)}
      >
        {QUEUE_SORT_OPTIONS.map((option) => (
          <option key={option.key} value={option.key}>
            {option.label}
          </option>
        ))}
      </Select>
    </div>
  );
}

function QueuePanel({
  candidatePage,
  isLoading,
  isError,
  error,
  selectedId,
  onSelect,
  viewState,
}) {
  const listRef = useRef(null);
  const candidates = candidatePage?.items;
  const statusCounts = candidatePage?.status_counts ?? {};
  const queueTotal = Object.values(statusCounts).reduce(
    (sum, count) => sum + count,
    0,
  );
  const statusTotal = viewState.statuses.length
    ? viewState.statuses.reduce(
        (sum, status) => sum + (statusCounts[status] ?? 0),
        0,
      )
    : queueTotal;

  function handlePageChange(page) {
    viewState.setPage(page);
    listRef.current?.scrollTo?.({ top: 0 });
  }

  return (
    <aside className="min-w-0 rounded-md border border-line bg-panel md:sticky md:top-15 md:col-start-1 md:row-start-1 md:flex md:max-h-[calc(100vh-4.75rem)] md:flex-col md:self-start">
      <div className="shrink-0 border-b border-line px-4 py-3">
        <h2 className="text-base font-semibold text-ink">Queue</h2>
        <div className="mt-2 space-y-2">
          <QueueSearch q={viewState.q} onSearch={viewState.setSearch} />
          <QueueControls
            statuses={viewState.statuses}
            onStatusesChange={viewState.setStatuses}
            sortKey={viewState.sortKey}
            onSortKeyChange={viewState.setSortKey}
          />
        </div>
      </div>

      <div ref={listRef} className="p-2 md:min-h-0 md:overflow-y-auto">
        {isLoading ? (
          <p className="px-2 py-3 text-sm text-ink-muted">
            Loading candidates…
          </p>
        ) : isError ? (
          <p className="px-2 py-3 text-sm text-danger">
            {error?.message ?? "Failed to load merge candidates."}
          </p>
        ) : candidates?.length ? (
          <div className="space-y-1">
            {candidates.map((item) => (
              <CandidateQueueItem
                key={item.id}
                candidate={item}
                isSelected={item.id === selectedId}
                onSelect={onSelect}
              />
            ))}
          </div>
        ) : queueTotal === 0 ? (
          <p className="px-2 py-3 text-sm text-ink-muted">
            No merge candidates to review.
          </p>
        ) : viewState.q && statusTotal > 0 ? (
          <p className="px-2 py-3 text-sm text-ink-muted">
            No candidates match this search. Try a different name, or clear the
            search.
          </p>
        ) : (
          <p className="px-2 py-3 text-sm text-ink-muted">
            No candidates match the selected statuses. Change the Status filter
            to see the others.
          </p>
        )}
      </div>

      {candidatePage?.total_count > 0 ? (
        <div className="shrink-0 border-t border-line px-3 pb-3">
          {}
          <Pagination
            page={viewState.page}
            pageSize={viewState.pageSize}
            totalCount={candidatePage.total_count}
            totalPages={candidatePage.total_pages}
            onPageChange={handlePageChange}
            onPageSizeChange={viewState.setPageSize}
            compact
          />
        </div>
      ) : null}
    </aside>
  );
}

function CandidateFacts({ candidate }) {
  return (
    <dl className="grid gap-3 text-sm sm:grid-cols-3">
      <div>
        <dt className="font-semibold text-ink-muted">Status</dt>
        <dd className="mt-1 text-ink">{candidate.status}</dd>
      </div>
      <div>
        <dt className="font-semibold text-ink-muted">Source resources</dt>
        <dd className="mt-1 break-words text-ink">
          {candidate.resource_ids.map((id, index) => (
            <span key={id}>
              {index > 0 ? ", " : null}
              <Link
                to={`/${ENDPOINT}/${id}`}
                className="text-primary underline"
              >
                {id}
              </Link>
            </span>
          ))}
        </dd>
      </div>
      <div>
        <dt className="font-semibold text-ink-muted">Merged resource</dt>
        <dd className="mt-1 break-words text-ink">
          {candidate.merged_resource_id ? (
            <Link
              to={`/${ENDPOINT}/${candidate.merged_resource_id}`}
              className="text-primary underline"
            >
              {candidate.merged_resource_id}
            </Link>
          ) : (
            "Not created"
          )}
        </dd>
      </div>
    </dl>
  );
}

function DecisionControls({
  reviewNotes,
  onReviewNotesChange,
  onReview,
  actionLoading,
  activeReviewAction,
}) {
  return (
    <section
      aria-label="Review decision"
      className="border-t border-line bg-surface px-5 py-4"
    >
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
        <div className="min-w-0">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <label
              htmlFor="decision-notes"
              className="text-sm font-semibold text-ink"
            >
              Decision notes
            </label>
            <span className="text-xs font-medium text-ink-muted">Optional</span>
          </div>
          <textarea
            id="decision-notes"
            value={reviewNotes}
            onChange={(event) => onReviewNotesChange(event.target.value)}
            rows={2}
            className="mt-2 min-h-[5.5rem] w-full rounded-md border border-line bg-panel px-3 py-2 text-sm leading-5 text-ink focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
            placeholder="Add rationale, uncertainty, or follow-up for the audit trail"
          />
        </div>

        <div className="flex flex-col gap-2 sm:flex-row lg:justify-end">
          <Button
            onClick={() => onReview("deny")}
            disabled={actionLoading}
            variant="danger"
            className="min-h-11"
          >
            {activeReviewAction === "deny" ? "Denying…" : "Deny merge"}
          </Button>
          <Button
            onClick={() => onReview("approve")}
            disabled={actionLoading}
            aria-describedby="decision-guidance"
            variant="confirm"
            className="min-h-11"
          >
            {activeReviewAction === "approve" ? "Approving…" : "Approve merge"}
          </Button>
        </div>
      </div>

      <p
        id="decision-guidance"
        className="mt-3 text-xs leading-5 text-ink-muted"
      >
        The decision and notes are recorded for review history.
      </p>
    </section>
  );
}

function CandidateDecisionPanel({
  selectedId,
  listCandidate,
  candidateQuery,
  reviewNotes,
  onReviewNotesChange,
  onReview,
  actionError,
  actionLoading,
  activeReviewAction,
}) {
  const {
    data: detailCandidate,
    isLoading: candidateLoading,
    isError: candidateError,
    error: candidateErrorObj,
  } = candidateQuery;

  const candidate = detailCandidate ?? listCandidate;
  const sourceDetails = useMergeSourceDetails(
    ENDPOINT,
    candidate?.resource_ids,
    !candidate?.merged_resource_id,
  );

  if (!selectedId) {
    return (
      <section className="rounded-md border border-line bg-panel p-5">
        <p className="text-sm text-ink-muted">Select a candidate.</p>
      </section>
    );
  }

  if (candidateError && !candidate) {
    return (
      <section className="rounded-md border border-line bg-panel p-5">
        <p className="text-sm text-danger">
          {candidateErrorObj?.message ?? "Failed to load candidate."}
        </p>
      </section>
    );
  }

  if (!candidate) {
    return (
      <section className="rounded-md border border-line bg-panel p-5">
        <p className="text-sm text-ink-muted">No candidate loaded.</p>
      </section>
    );
  }

  return (
    <article className="min-w-0 overflow-hidden rounded-md border border-line bg-panel">
      {candidateError ? (
        <p className="border-b border-danger/25 bg-danger-soft px-5 py-4 text-sm text-danger">
          These details could not be refreshed and may be out of date.{" "}
          {candidateErrorObj?.message ?? "Failed to load candidate."}
        </p>
      ) : null}

      <div className="space-y-4 px-5 py-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="break-words text-2xl font-semibold text-ink">
              {candidateDisplayName(candidate)}
            </h2>
            <p className="mt-1 text-sm text-ink-muted">
              Decide whether these resources should become one curated record.
            </p>
          </div>
          <StatusBadge status={candidate.status} />
        </div>

        <CandidateFacts candidate={candidate} />

        {candidate.review_notes ? (
          <div className="rounded-md border border-line bg-surface p-3 text-sm text-ink">
            <span className="font-medium">Existing notes:</span>{" "}
            {candidate.review_notes}
          </div>
        ) : null}

        {candidate.status !== "PENDING" ? (
          <p className="rounded-md border border-line bg-surface p-3 text-sm text-ink-muted">
            This candidate has already been reviewed.
          </p>
        ) : null}
      </div>

      {candidate.merged_resource_id ? (
        <MergedResourceView
          endpoint={ENDPOINT}
          resourceId={candidate.merged_resource_id}
        />
      ) : (
        <MergeSourceComparison
          resourceIds={candidate.resource_ids}
          compare={detailCandidate?.compare}
          isLoading={candidateLoading}
          isError={candidateError}
          error={candidateErrorObj}
          sourceDetails={sourceDetails}
        />
      )}

      {candidate.status === "PENDING" ? (
        <DecisionControls
          reviewNotes={reviewNotes}
          onReviewNotesChange={onReviewNotesChange}
          onReview={onReview}
          actionLoading={actionLoading}
          activeReviewAction={activeReviewAction}
        />
      ) : null}

      {actionError ? (
        <p className="border-t border-danger/25 bg-danger-soft px-5 py-4 text-sm text-danger">
          {actionError}
        </p>
      ) : null}
    </article>
  );
}

export default function MergeCandidateReviewPage() {
  useDocumentTitle("Merge review");
  const viewState = useMergeReviewState();
  const [selectedId, setSelectedId] = useState(null);
  const [reviewNotes, setReviewNotes] = useState("");
  const [notesCandidateId, setNotesCandidateId] = useState(selectedId);
  if (notesCandidateId !== selectedId) {
    setNotesCandidateId(selectedId);
    setReviewNotes("");
  }
  const selectedPanelRef = useRef(null);

  const reviewMutation = useReviewMergeCandidate(ENDPOINT);
  const actionLoading = reviewMutation.isPending;
  const activeReviewAction = reviewMutation.isPending
    ? reviewMutation.variables?.action
    : null;
  const { reset: resetReview } = reviewMutation;
  useEffect(() => {
    resetReview();
  }, [selectedId, resetReview]);
  const actionError =
    reviewMutation.error && reviewMutation.variables?.id === selectedId
      ? reviewMutation.error.message || String(reviewMutation.error)
      : null;

  const {
    data: candidatePage,
    isLoading: listLoading,
    isError: listError,
    error: listErrorObj,
    isPlaceholderData: listIsPlaceholder,
    isFetching: listIsFetching,
  } = useMergeCandidates(ENDPOINT, toMergeCandidateQuery(viewState), true);
  const pageCandidates = candidatePage?.items;

  const lastPage = Math.max(candidatePage?.total_pages ?? 0, 1);
  const pastLastPage =
    Boolean(candidatePage) &&
    !listIsPlaceholder &&
    !listIsFetching &&
    viewState.page > lastPage;
  const { setPage } = viewState;
  useEffect(() => {
    if (pastLastPage) setPage(lastPage, { replace: true });
  }, [pastLastPage, lastPage, setPage]);

  const selectionOnPage = pageCandidates?.some((c) => c.id === selectedId);
  if (pageCandidates && !selectionOnPage && !listIsPlaceholder) {
    if (pageCandidates.length) {
      const firstPending = pageCandidates.find((c) => c.status === "PENDING");
      setSelectedId(firstPending?.id ?? pageCandidates[0].id);
    } else if (selectedId !== null) {
      setSelectedId(null);
    }
  }

  const candidateQuery = useMergeCandidate(
    ENDPOINT,
    selectedId,
    Boolean(selectedId),
  );
  const listCandidate =
    pageCandidates?.find((item) => item.id === selectedId) ?? null;
  const candidate = candidateQuery.data ?? listCandidate;

  const statusCounts = candidatePage?.status_counts;
  const pendingCount = statusCounts?.PENDING ?? 0;
  const reviewedCount =
    (statusCounts?.APPROVED ?? 0) + (statusCounts?.DENIED ?? 0);
  const totalCount = pendingCount + reviewedCount;

  function handleSelect(id) {
    setSelectedId(id);
    const panel = selectedPanelRef.current;
    panel?.focus({ preventScroll: true });
    if (!window.matchMedia(TWO_COLUMN_LAYOUT_QUERY).matches) {
      panel?.scrollIntoView({ block: "start" });
    }
    setReviewNotes("");
    reviewMutation.reset();
  }

  function handleReview(action) {
    if (!candidate?.id) return;

    reviewMutation.mutate(
      { id: candidate.id, action, reviewNotes },
      {
        onSuccess: () => {
          const nextPending = pageCandidates?.find(
            (item) => item.id !== candidate.id && item.status === "PENDING",
          );
          if (nextPending) {
            setSelectedId(nextPending.id);
          }
          setReviewNotes("");
        },
      },
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header className="border-b border-line pb-4">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-ink">
              Merge review
            </h1>
            <p className="mt-2 text-sm text-ink-muted">
              Review one candidate at a time.
            </p>
          </div>
          <dl className="flex flex-wrap gap-3 text-sm">
            <div className="rounded-md border border-line bg-panel px-3 py-2">
              <dt className="text-xs text-ink-muted">Pending</dt>
              <dd className="font-mono text-lg font-medium tabular-nums text-ink">
                {pendingCount}
              </dd>
            </div>
            <div className="rounded-md border border-line bg-panel px-3 py-2">
              <dt className="text-xs text-ink-muted">Reviewed</dt>
              <dd className="font-mono text-lg font-medium tabular-nums text-ink">
                {reviewedCount}
              </dd>
            </div>
            <div className="rounded-md border border-line bg-panel px-3 py-2">
              <dt className="text-xs text-ink-muted">Total</dt>
              <dd className="font-mono text-lg font-medium tabular-nums text-ink">
                {totalCount}
              </dd>
            </div>
          </dl>
        </div>
      </header>

      <div className="grid gap-6 md:grid-cols-[16rem_minmax(0,1fr)] lg:grid-cols-[20rem_minmax(0,1fr)]">
        <div
          ref={selectedPanelRef}
          role="region"
          aria-label="Selected candidate"
          tabIndex={-1}
          className="min-w-0 rounded-md focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:ring-offset-2 md:col-start-2 md:row-start-1"
        >
          <CandidateDecisionPanel
            selectedId={selectedId}
            listCandidate={listCandidate}
            candidateQuery={candidateQuery}
            reviewNotes={reviewNotes}
            onReviewNotesChange={setReviewNotes}
            onReview={handleReview}
            actionError={actionError}
            actionLoading={actionLoading}
            activeReviewAction={activeReviewAction}
          />
        </div>

        <QueuePanel
          candidatePage={candidatePage}
          isLoading={listLoading}
          isError={listError}
          error={listErrorObj}
          selectedId={selectedId}
          onSelect={handleSelect}
          viewState={viewState}
        />
      </div>
    </div>
  );
}
