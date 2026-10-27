export function compareEntry(compare, field) {
  return compare?.find((entry) => entry.field === field) ?? null;
}

export function valueEntryForResource(entry, resourceId) {
  return entry?.values.find((v) => v.resource_id === resourceId) ?? null;
}

export function pickCompareName(compare) {
  const winner = compareEntry(compare, "name")?.values[0]?.value;
  return winner == null || winner === "" ? null : winner;
}
