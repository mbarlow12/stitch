const nameCollator = new Intl.Collator(undefined, { sensitivity: "base" });

const STATUS_ORDER = ["PENDING", "DENIED", "APPROVED"];

function statusRank(status) {
  const index = STATUS_ORDER.indexOf(status);
  return index === -1 ? STATUS_ORDER.length : index;
}

export function sortCandidates(candidates, sort, namesById) {
  if (sort === "oldest") return [...candidates].reverse();
  if (sort === "status") {
    return [...candidates].sort(
      (a, b) => statusRank(a.status) - statusRank(b.status),
    );
  }
  if (sort !== "name-asc" && sort !== "name-desc") return [...candidates];

  const direction = sort === "name-desc" ? -1 : 1;
  const apiOrder = new Map(
    candidates.map((candidate, index) => [candidate.id, index]),
  );

  return [...candidates].sort((a, b) => {
    const nameA = namesById.get(a.id);
    const nameB = namesById.get(b.id);
    const aLoaded = nameA != null;
    const bLoaded = nameB != null;

    if (aLoaded !== bLoaded) return aLoaded ? -1 : 1;
    if (aLoaded) {
      const byName = nameCollator.compare(nameA, nameB) * direction;
      if (byName !== 0) return byName;
    }
    return apiOrder.get(a.id) - apiOrder.get(b.id);
  });
}
