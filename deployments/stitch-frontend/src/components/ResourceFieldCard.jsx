import { useMemo, useState } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useQueryClient } from "@tanstack/react-query";
import { FieldCard } from "./FieldCard";
import Button from "./Button";
import Input from "./Input";
import {
  useCreateSourceForResource,
  useFieldSourceValues,
} from "../hooks/useResources";
import {
  useHasPermission,
  useHasAllPermissions,
} from "../hooks/usePermissions";
import { useConfig } from "../config/useConfig";
import { createAuthenticatedFetcher } from "../auth/api";
import { updateFieldSourcePriority } from "../queries/api";
import { resourceQueries } from "../queries/resources";
import {
  SOURCES,
  SOURCE_COLORS,
  SOURCE_LABELS,
  UNKNOWN_SOURCE_LABEL,
  DEFAULT_FIELD_COLOR,
} from "../constants/sourceMeta";
import { FIELD_META } from "../constants/fieldMeta";

const RESOURCE_WRITE = "resource:write";
const ALL_SOURCE_READ_PERMISSIONS = SOURCES.map(
  (source) => `source:read:${source}`,
);

function arraysEqual(a, b) {
  return a.length === b.length && a.every((value, index) => value === b[index]);
}

function buildRmiSourcePayload({ fieldKey, value, note }) {
  return {
    source: "rmi",
    name: null,
    country: null,
    [fieldKey]: value,
    source_record: {
      record_id: null,
      run_id: null,
      observed_at: new Date().toISOString(),
      producer: "stitch-frontend",
      payload: { action: "field_overwrite", field: fieldKey, value, note },
    },
  };
}

function SourceValueRow({
  source,
  value,
  sourceId,
  isWinner,
  isOverride,
  editControls,
}) {
  const barColor = SOURCE_COLORS[source] ?? DEFAULT_FIELD_COLOR;
  const sourceLabel = SOURCE_LABELS[source] ?? UNKNOWN_SOURCE_LABEL;
  const meta =
    sourceId !== null && sourceId !== undefined
      ? `${sourceLabel} · #${sourceId}`
      : sourceLabel;
  const display = typeof value === "string" ? `"${value}"` : String(value);

  return (
    <div
      className={`flex items-center gap-2 rounded-md border border-line border-l-4 px-2.5 py-1.5 ${
        isWinner ? "bg-surface" : "bg-panel"
      }`}
      style={{ borderLeftColor: barColor }}
    >
      <div className="min-w-0 flex-1">
        <div className="break-words text-sm text-ink">{display}</div>
        <div className="mt-0.5 text-xs text-ink-muted">
          {meta}
          {isOverride && (
            <span className="ml-1.5 rounded bg-rmiblue-100 px-1 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-bluespruce">
              curated
            </span>
          )}
        </div>
      </div>
      {editControls}
    </div>
  );
}

function MoveButtons({ onMoveUp, onMoveDown, canMoveUp, canMoveDown, label }) {
  return (
    <div className="flex flex-col gap-0.5">
      <button
        type="button"
        onClick={onMoveUp}
        disabled={!canMoveUp}
        aria-label={`Move ${label} up`}
        className="rounded border border-line px-1.5 text-xs leading-4 text-ink-muted hover:bg-rmiblue-100 disabled:cursor-not-allowed disabled:opacity-40"
      >
        ↑
      </button>
      <button
        type="button"
        onClick={onMoveDown}
        disabled={!canMoveDown}
        aria-label={`Move ${label} down`}
        className="rounded border border-line px-1.5 text-xs leading-4 text-ink-muted hover:bg-rmiblue-100 disabled:cursor-not-allowed disabled:opacity-40"
      >
        ↓
      </button>
    </div>
  );
}

function AddSourceForm({ endpoint, resourceId, fieldKey, onSaved }) {
  const createSource = useCreateSourceForResource(endpoint);
  const allowedValues = FIELD_META[fieldKey]?.options;

  const [value, setValue] = useState("");
  const [note, setNote] = useState("");

  const trimmedValue = value.trim();
  const isSaving = createSource.isPending;
  const saveError = createSource.error
    ? createSource.error.message || "Failed to add value."
    : "";

  async function handleSave() {
    if (!trimmedValue || isSaving) return;

    const payload = buildRmiSourcePayload({
      fieldKey,
      value: trimmedValue,
      note: note.trim() || null,
    });

    try {
      await createSource.mutateAsync({ resourceId, payload });
      onSaved();
    } catch {
      return;
    }
  }

  return (
    <div className="space-y-2 rounded-md border border-line bg-surface p-2">
      {allowedValues ? (
        <select
          value={value}
          onChange={(event) => setValue(event.target.value)}
          aria-label="New value"
          className="min-h-9 w-full rounded-md border border-line bg-panel px-3 py-2 text-sm text-ink transition-colors hover:border-line-strong focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
        >
          <option value="" disabled>
            Select a value
          </option>
          {allowedValues.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      ) : (
        <Input
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="New value"
          aria-label="New value"
          className="w-full"
        />
      )}
      <Input
        value={note}
        onChange={(event) => setNote(event.target.value)}
        placeholder="Note (optional)"
        aria-label="Note"
        className="w-full"
      />
      <div className="flex items-center gap-2">
        <Button
          variant="primary"
          onClick={handleSave}
          disabled={!trimmedValue || isSaving}
        >
          {isSaving ? "Saving…" : "Save"}
        </Button>
      </div>
      {saveError && <p className="text-sm text-danger">{saveError}</p>}
    </div>
  );
}

function FieldSourcesPanel({
  isLoading,
  isError,
  sources,
  canEdit,
  endpoint,
  resourceId,
  fieldKey,
}) {
  const canWriteResource = useHasPermission(RESOURCE_WRITE);
  const canReadAllSources = useHasAllPermissions(ALL_SOURCE_READ_PERMISSIONS);
  const config = useConfig();
  const { getAccessTokenSilently } = useAuth0();
  const queryClient = useQueryClient();

  const [isEditing, setIsEditing] = useState(false);
  const [isAdding, setIsAdding] = useState(false);
  const [workingOrder, setWorkingOrder] = useState([]);
  const [baselineOrder, setBaselineOrder] = useState([]);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState("");

  const originalOrder = useMemo(
    () => sources.map((row) => row.source_id),
    [sources],
  );
  const sourcesById = useMemo(
    () => new Map(sources.map((row) => [row.source_id, row])),
    [sources],
  );

  const canReorder =
    canWriteResource && canReadAllSources && sources.length > 1;
  const canEnterEdit = canReorder || canEdit;
  const orderChanged = isEditing && !arraysEqual(workingOrder, baselineOrder);
  const sourcesChanged =
    isEditing && !arraysEqual(baselineOrder, originalOrder);

  function beginEdit() {
    setWorkingOrder(originalOrder);
    setBaselineOrder(originalOrder);
    setSaveError("");
    setIsEditing(true);
  }

  function stopEditing() {
    setIsEditing(false);
    setIsAdding(false);
    setSaveError("");
  }

  function move(index, delta) {
    setWorkingOrder((current) => {
      const target = index + delta;
      if (target < 0 || target >= current.length) return current;
      const next = [...current];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  }

  async function handleSaveOrder() {
    setIsSaving(true);
    setSaveError("");
    try {
      const fetcher = createAuthenticatedFetcher(
        config,
        getAccessTokenSilently,
      );
      await updateFieldSourcePriority(
        config,
        resourceId,
        fieldKey,
        workingOrder,
        fetcher,
        endpoint,
      );
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: resourceQueries.fieldSources(
            config,
            endpoint,
            resourceId,
            fieldKey,
          ).queryKey,
        }),
        queryClient.invalidateQueries({
          queryKey: resourceQueries.detail(config, endpoint, resourceId)
            .queryKey,
        }),
      ]);
      stopEditing();
    } catch (err) {
      setSaveError(err.message || "Failed to save source order.");
    } finally {
      setIsSaving(false);
    }
  }

  const displayRows = isEditing
    ? workingOrder.map((id) => sourcesById.get(id)).filter(Boolean)
    : sources;

  return (
    <div className="mt-2 space-y-2 rounded-md border border-line bg-panel p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
          All sources
        </p>
        {!isEditing && canEnterEdit && (
          <Button variant="ghost" className="px-2 py-1" onClick={beginEdit}>
            Edit
          </Button>
        )}
        {isEditing && (
          <div className="ml-auto flex items-center gap-2">
            <Button
              variant="ghost"
              className="px-2 py-1"
              onClick={stopEditing}
              disabled={isSaving}
            >
              Cancel
            </Button>
            {canReorder && (
              <Button
                variant="primary"
                className="px-2 py-1"
                onClick={handleSaveOrder}
                disabled={!orderChanged || isSaving || sourcesChanged}
              >
                {isSaving ? "Saving…" : "Save"}
              </Button>
            )}
          </div>
        )}
      </div>
      {saveError && <p className="text-sm text-danger">{saveError}</p>}
      {sourcesChanged && (
        <p className="text-sm text-warning">
          The source list changed. Cancel and re-open to edit the current order.
        </p>
      )}
      {isEditing &&
        canEdit &&
        (isAdding ? (
          <AddSourceForm
            endpoint={endpoint}
            resourceId={resourceId}
            fieldKey={fieldKey}
            onSaved={stopEditing}
          />
        ) : (
          <Button
            variant="secondary"
            onClick={() => setIsAdding(true)}
            aria-label="Add value"
          >
            +
          </Button>
        ))}
      {isLoading && <p className="text-sm text-ink-muted">Loading sources…</p>}
      {isError && (
        <p className="text-sm text-danger">Failed to load source values.</p>
      )}
      {!isLoading && !isError && sources.length === 0 && (
        <p className="text-sm text-ink-muted">
          No source values for this field.
        </p>
      )}
      {!isLoading && !isError && sources.length > 0 && (
        <div className="space-y-1.5">
          {displayRows.map((row, idx) => (
            <SourceValueRow
              key={`${row.source}-${row.source_id}`}
              source={row.source}
              value={row.value}
              sourceId={row.source_id}
              isWinner={idx === 0}
              isOverride={!isEditing && row.is_override}
              editControls={
                isEditing && canReorder ? (
                  <MoveButtons
                    label={SOURCE_LABELS[row.source] ?? UNKNOWN_SOURCE_LABEL}
                    canMoveUp={idx > 0}
                    canMoveDown={idx < displayRows.length - 1}
                    onMoveUp={() => move(idx, -1)}
                    onMoveDown={() => move(idx, 1)}
                  />
                ) : null
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function ResourceFieldCard({
  endpoint,
  resourceId,
  fieldKey,
  label,
  value,
  source,
}) {
  const [isOpen, setIsOpen] = useState(false);
  const canWriteSource = useHasPermission("source:write");
  const canWriteResource = useHasPermission("resource:write");
  const canEdit = canWriteSource && canWriteResource;

  const hasValue = value !== null && value !== undefined && value !== "";
  const expandable = hasValue || canEdit;
  const { data, isLoading, isError } = useFieldSourceValues(
    endpoint,
    resourceId,
    fieldKey,
    isOpen && expandable,
  );

  return (
    <FieldCard
      label={label}
      value={value}
      source={source}
      expandable={expandable}
      isOpen={isOpen}
      onToggle={() => setIsOpen((current) => !current)}
    >
      <FieldSourcesPanel
        isLoading={isLoading}
        isError={isError}
        sources={data ?? []}
        canEdit={canEdit}
        endpoint={endpoint}
        resourceId={resourceId}
        fieldKey={fieldKey}
      />
    </FieldCard>
  );
}
