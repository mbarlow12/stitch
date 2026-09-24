from itertools import combinations
from rapidfuzz import process, fuzz
from dataclasses import dataclass, field
from typing import NamedTuple, TypeGuard, Final
from collections import defaultdict, Counter
import math

import numpy as np

from .model import PreparedItem, CandidateGroup, Signals, ConfidenceScore, ConfidenceStr

EARTH_RADIUS_KM = 6371.0088


FUZZY_NAME = "fuzzy-name"
GEO_PROXIMITY = "geo-proximity"
EXACT_NAME = "exact-normalized-name"

CONFIDENCE_ORDER: Final[dict[ConfidenceStr, ConfidenceScore]] = {
    "high": 0,
    "medium": 1,
    "low": 2,
}

# Tokens that turn one field into a *different* field: 'blueberry east' is not
# 'blueberry west'. If such a token is on one side of a pair and not the other,
# the two are distinct assets no matter how similar the strings look.
QUALIFIER_TOKENS = frozenset(
    "north south east west n s e w ne nw se sw "
    "northeast northwest southeast southwest "
    "central upper lower deep shallow main extension ext unit "
    "i ii iii iv v vi".split()
)


Pair = tuple[int, int]


class Edge(NamedTuple):
    """One pass proposing one link, with the evidence it found."""

    left: int
    right: int
    reason: str
    score: int
    distance_km: float | None = None


@dataclass
class PairEvidence:
    """Everything every pass noticed about one pair, folded together."""

    reasons: set[str] = field(default_factory=set)
    score: int = 0
    distance_km: float | None = None


class UnionFind:
    def __init__(self) -> None:
        self._parent: dict[int, int] = {}
        self._size: dict[int, int] = {}

    def find(self, item: int) -> int:
        self._parent.setdefault(item, item)
        self._size.setdefault(item, 1)
        root = item
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[item] != root:
            self._parent[item], item = root, self._parent[item]
        return root

    def size_of(self, item: int) -> int:
        return self._size[self.find(item)]

    def union(self, left: int, right: int) -> bool:
        """Merge two clusters. Returns False if they were already together."""
        left_root, right_root = self.find(left), self.find(right)
        if left_root == right_root:
            return False
        self._parent[right_root] = left_root
        self._size[left_root] += self._size[right_root]
        return True

    def groups(self) -> dict[int, list[int]]:
        clusters: dict[int, list[int]] = defaultdict(list)
        for item in self._parent:
            clusters[self.find(item)].append(item)
        return clusters


def key_anchors_pair(key: str, left: PreparedItem, right: PreparedItem) -> bool:
    """May ``key`` join these two records?

    Always yes when it is a whole name, or when either side is a single-segment
    name (the bare-name-versus-decorated-name case this tool exists for).
    Otherwise the key must be the rarest segment on *both* sides.
    """
    if key in (left.core, right.core):
        return True
    if len(left.segments) == 1 or len(right.segments) == 1:
        return True
    return key in left.anchors and key in right.anchors


def exact_edges(
    prepared: list[PreparedItem], max_key_frequency: int = 6
) -> tuple[list[Edge], list[tuple[str, int]]]:
    """Pairs sharing a blocking key, ignoring keys too common to discriminate."""
    by_key: dict[str, list[int]] = defaultdict(list)
    for index, record in enumerate(prepared):
        for key in record.keys:
            by_key[key].append(index)

    edges: list[Edge] = []
    suppressed: list[tuple[str, int]] = []
    for key, indexes in by_key.items():
        if len(indexes) < 2:
            continue
        if len(indexes) > max_key_frequency:
            suppressed.append((key, len(indexes)))
            continue
        for left, right in combinations(indexes, 2):
            if key_anchors_pair(key, prepared[left], prepared[right]):
                # The key matched character for character, so there is no
                # similarity to measure: this pair scores a flat 100.
                edges.append(Edge(left, right, EXACT_NAME, 100))
    return edges, sorted(suppressed, key=lambda pair: -pair[1])


def similarity_edges(
    prepared: list[PreparedItem],
    fuzzy_threshold: int = 90,
    geo_name_threshold: int = 70,
    geo_km: float = 10.0,
) -> list[Edge]:
    """Fuzzy and geo pairs, computed per country bucket off one cdist matrix."""
    buckets: dict[str | None, list[int]] = defaultdict(list)
    for index, record in enumerate(prepared):
        buckets[record.country].append(index)

    edges: list[Edge] = []
    floor = min(fuzzy_threshold, geo_name_threshold)

    for indexes in buckets.values():
        if len(indexes) < 2:
            continue
        cores = [prepared[index].core for index in indexes]
        scores = process.cdist(
            cores,
            cores,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=floor,
            workers=-1,
        )
        left_positions, right_positions = np.nonzero(np.triu(scores, k=1))
        for left_position, right_position in zip(left_positions, right_positions):
            left = indexes[int(left_position)]
            right = indexes[int(right_position)]
            score = int(scores[left_position, right_position])
            if score >= fuzzy_threshold:
                edges.append(Edge(left, right, FUZZY_NAME, score))
                continue
            # Too loosely named to join on the name alone, so let the map
            # decide: same country, similar name, within --geo-km of each other.
            distance = pair_distance_km(prepared[left], prepared[right])
            if distance is not None and distance <= geo_km:
                edges.append(Edge(left, right, GEO_PROXIMITY, score, distance))
    return edges


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _no_none_in_tuple[T](
    vals: tuple[T | None, ...],
) -> TypeGuard[tuple[T, ...]]:
    if None in vals:
        return False
    return True


def pair_distance_km(left: PreparedItem, right: PreparedItem) -> float | None:
    vals: tuple[float | None, ...] = (
        left.latitude,
        left.longitude,
        right.latitude,
        right.longitude,
    )
    if _no_none_in_tuple(vals):
        return haversine_km(*vals)
    return None


def build_groups(
    prepared: list[PreparedItem],
    edges: list[Edge],
    max_group_size: int = 2,
) -> tuple[list[CandidateGroup], list[Pair]]:
    """Cluster the surviving edges, then assemble reviewable groups."""
    evidence = collect_evidence(prepared, edges)
    union, deferred = cluster_pairs(evidence, max_group_size)

    groups: list[CandidateGroup] = []
    for members in union.groups().values():
        if len(members) < 2:
            continue
        members = sorted(members, key=lambda index: prepared[index].id)
        entries: list[PairEvidence] = []
        for left, right in combinations(members, 2):
            entry = evidence.get((min(left, right), max(left, right)))
            if entry is not None:
                entries.append(entry)
        records = [prepared[index] for index in members]
        groups.append(describe_group(records, entries))

    groups.sort(key=group_rank)
    return groups, deferred


def collect_evidence(
    prepared: list[PreparedItem], edges: list[Edge]
) -> dict[Pair, PairEvidence]:
    """Fold every pass's edges into one entry per surviving pair."""
    evidence: dict[Pair, PairEvidence] = {}
    for edge in edges:
        if edge_vetoed(prepared[edge.left], prepared[edge.right]):
            continue
        pair = (min(edge.left, edge.right), max(edge.left, edge.right))
        entry = evidence.setdefault(pair, PairEvidence())
        entry.reasons.add(edge.reason)
        entry.score = max(entry.score, edge.score)
        if edge.distance_km is not None:
            entry.distance_km = edge.distance_km
    return evidence


def cluster_pairs(
    evidence: dict[Pair, PairEvidence], max_group_size: int
) -> tuple[UnionFind, list[Pair]]:
    """Agglomerate the pairs, strongest edge first.

    Any join that would push a cluster past --max-group-size is refused.
    Dropping whole oversized components (the obvious alternative) silently
    discards the strong exact-name pairs buried inside a geo-chained blob, so
    instead the weakest edges are the ones that lose. Ties break on record
    order, so a run is reproducible.
    """

    def edge_strength(pair: Pair) -> tuple[int, int, int, int]:
        entry = evidence[pair]
        if EXACT_NAME in entry.reasons:
            tier = 3
        elif FUZZY_NAME in entry.reasons:
            tier = 2
        else:
            tier = 1
        return (-tier, -entry.score, pair[0], pair[1])

    union = UnionFind()
    deferred: list[Pair] = []
    for pair in sorted(evidence, key=edge_strength):
        left, right = pair
        if union.find(left) == union.find(right):
            continue
        if union.size_of(left) + union.size_of(right) > max_group_size:
            deferred.append(pair)
            continue
        union.union(left, right)
    return union, deferred


def describe_group(
    records: list[PreparedItem], entries: list[PairEvidence]
) -> CandidateGroup:
    """One reviewable group: who is in it, why, and how much to trust it."""
    similarities = [entry.score for entry in entries]
    distances = [
        entry.distance_km for entry in entries if entry.distance_km is not None
    ]
    countries = sorted({r.country for r in records if r.country})

    signal_args = {
        "normalized_names": sorted({r.core for r in records if r.core}),
        "min_name_similarity": min(similarities) if similarities else None,
        "countries": countries,
        "same_country": len(countries) <= 1,
        "max_distance_km": round(max(distances), 2) if distances else None,
        "discriminators": sorted({d for r in records for d in r.discriminators}),
    }

    rids = [r.id for r in records]
    reasons = sorted({reason for entry in entries for reason in entry.reasons})
    signals = Signals(**signal_args)
    return CandidateGroup(
        resource_ids=rids,
        reasons=reasons,
        signals=signals,
        confidence=classify_confidence(rids, reasons, signals),
    )


def group_rank(group: CandidateGroup) -> tuple[int, bool, bool, int, int]:
    """Most trustworthy first: exact-key, cross-source, same-country, tightest."""
    signals = group.signals
    return (
        CONFIDENCE_ORDER[group.confidence],
        EXACT_NAME not in group.reasons,
        not signals.same_country,
        -(signals.min_name_similarity or 0),
        len(group.resource_ids),
    )


def edge_vetoed(left: PreparedItem, right: PreparedItem) -> bool:
    return discriminators_conflict(left, right) or qualifiers_conflict(left, right)


def discriminators_conflict(left: PreparedItem, right: PreparedItem) -> bool:
    """Two records with different rare parentheticals are different assets."""
    left_set, right_set = left.discriminators, right.discriminators
    if not left_set or not right_set:
        return False
    return left_set.isdisjoint(right_set)


def qualifiers_conflict(left: PreparedItem, right: PreparedItem) -> bool:
    """One side carries a directional/ordinal token the other does not."""
    only_one_side = left.tokens.symmetric_difference(right.tokens)
    return any(token in QUALIFIER_TOKENS or token.isdigit() for token in only_one_side)


def split_by_confidence(
    groups: list[CandidateGroup], min_confidence: ConfidenceStr = "medium"
) -> tuple[list[CandidateGroup], Counter]:
    """Partition into the groups worth emitting now and a count of the rest."""
    limit = CONFIDENCE_ORDER[min_confidence]
    kept: list[CandidateGroup] = []
    withheld: Counter = Counter()
    for group in groups:
        if CONFIDENCE_ORDER[group.confidence] <= limit:
            kept.append(group)
        else:
            withheld[group.confidence] += 1
    return kept, withheld


def classify_confidence(
    resource_ids: list[int], reasons: list[str], signals: Signals
) -> ConfidenceStr:
    """How much a group deserves to be trusted without close reading.

    'high' is the pass-one tier: a clean two-record pair, joined on an exact
    normalized name, in one country, contributed by two different sources. That
    is the bare-name-versus-decorated-name duplicate this tool was built for,
    and it is the shape entity-linkage misses entirely today.
    """
    exact = EXACT_NAME in reasons
    size = len(resource_ids)
    similarity = signals.min_name_similarity or 0

    if exact and size == 2 and signals.same_country and not signals.discriminators:
        return "high"
    if exact and size <= 3 and signals.same_country:
        return "medium"
    if similarity >= 95 and size == 2 and signals.same_country:
        return "medium"
    return "low"
