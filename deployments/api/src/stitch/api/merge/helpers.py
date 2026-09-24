from __future__ import annotations
from dataclasses import asdict

import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from .model import OilGasFieldMatchRecord, PreparedItem

# Longest first: stripping is repeated until nothing more matches.
TYPE_PHRASES = (
    "oil and gas field",
    "oil and gas asset",
    "cbm gas field",
    "tight gas field",
    "oil and gas",
    "oil field",
    "gas field",
    "oil asset",
    "gas asset",
    "oil phase",
    "gas phase",
    "field",
    "asset",
    "phase",
)

# "10097UUU/Athabasca Oil Asset (Alberta, Canada)" -> drop the record-id prefix.
ID_PREFIX_RE = re.compile(r"^\s*\d+[A-Za-z]*\s*/\s*")
PARENTHETICAL_RE = re.compile(r"\(([^()]*)\)")
SEGMENT_SPLIT_RE = re.compile(r"\s+-\s+")
PUNCT_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)
WHITESPACE_RE = re.compile(r"\s+")


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def tidy(text: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace."""
    cleaned = PUNCT_RE.sub(" ", strip_accents(text).casefold())
    return WHITESPACE_RE.sub(" ", cleaned).strip()


def strip_type_phrases(text: str) -> str:
    """Repeatedly remove trailing asset-type words: 'darquain oil field' -> 'darquain'."""
    current = text
    changed = True
    while changed:
        changed = False
        for phrase in TYPE_PHRASES:
            if current.endswith(" " + phrase):
                current = current[: -(len(phrase) + 1)].strip()
                changed = True
                break
    return current


def split_name(raw_name: str) -> tuple[list[str], list[str]]:
    """Split a raw name into (segments, parentheticals).

    Parentheticals are pulled out wherever they appear; the remaining text is
    split on ' - ' into segments, each tidied and stripped of type phrases.
    """
    without_prefix = ID_PREFIX_RE.sub("", raw_name)
    parentheticals = [
        tidy(match) for match in PARENTHETICAL_RE.findall(without_prefix) if tidy(match)
    ]
    body = PARENTHETICAL_RE.sub(" ", without_prefix)

    segments = []
    for part in SEGMENT_SPLIT_RE.split(body):
        segment = strip_type_phrases(tidy(part))
        if segment:
            segments.append(segment)
    return segments, parentheticals


def name_keys(segments: list[str]) -> list[str]:
    """Blocking keys for a name.

    The whole core, plus each ' - ' segment on its own, because GEM writes both
    '<Place> - <Operator> Gas Asset' and '<Operator> - <Place> Gas Asset' and we
    cannot reliably tell which half is the field.
    """
    if not segments:
        return []
    keys = {" ".join(segments)}
    if len(segments) > 1:
        keys.update(segments)
    return sorted(keys)


def load_records(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def prepare(
    records: Iterable[OilGasFieldMatchRecord], location_min_count: int = 5
) -> list[PreparedItem]:
    """Attach normalized keys and discriminators to each record."""
    prepared: list[PreparedItem] = []
    for record in records:
        segments, parentheticals = split_name(record.name or "")
        core = " ".join(segments)
        prepared.append(
            PreparedItem(
                **asdict(record),
                segments=segments,
                core=core,
                tokens=frozenset(core.split()),
                parentheticals=parentheticals,
                keys=name_keys(segments),
            )
        )

    attach_discriminators(prepared, location_min_count)
    attach_anchors(prepared)
    return prepared


def attach_discriminators(
    prepared: list[PreparedItem], location_min_count: int
) -> None:
    """Mark the rare parentheticals on each record.

    A parenthetical seen on many records is boilerplate location text
    ("(iran)", "(alberta canada)"). A rare one discriminates ("(lamadian)",
    "(mc782)") and must block a join. This is learned from the corpus rather
    than from a hardcoded country list.
    """
    counts = Counter(
        paren for record in prepared for paren in set(record.parentheticals)
    )
    for i in range(len(prepared)):
        r = prepared[i]
        disc = frozenset(
            paren for paren in r.parentheticals if counts[paren] < location_min_count
        )
        prepared[i] = PreparedItem(**asdict(r), discriminators=disc)


def attach_anchors(prepared: list[PreparedItem]) -> None:
    """Mark the rarest segment(s) of each name.

    In '<A> - <B> Gas Asset' one half is the field and the other is the
    operator, and GEM writes it both ways round. The operator half recurs
    across many assets, the field half does not, so the rarest segment of a
    name is its anchor. Joining on a non-anchor segment is what produces
    'Belmont County - Ascent' ~ 'Harrison County - Ascent': two different
    fields sharing an operator.
    """
    segment_counts = Counter(
        segment for record in prepared for segment in set(record.segments)
    )
    for i in range(len(prepared)):
        record = prepared[i]
        segments = record.segments
        if not segments:
            continue
        rarest = min(segment_counts[segment] for segment in segments)
        anchors = frozenset(
            segment for segment in segments if segment_counts[segment] == rarest
        )
        prepared[i] = PreparedItem(**asdict(record), anchors=anchors)
