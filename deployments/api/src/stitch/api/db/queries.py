
from __future__ import annotations

from collections.abc import Callable, Collection
from typing import Any, Final, Literal

from sqlalchemy import (
    CTE,
    ColumnElement,
    Select,
    and_,
    asc,
    case,
    desc,
    func,
    or_,
    select,
)

from stitch.api.db.model import (
    MembershipModel,
    MembershipStatus,
    OGFieldResourceSourcePriority,
    OGFieldResourceState,
    OGFieldSourcePriority,
    OilGasFieldSourceModel,
    OilGasFieldSourceValueModel,
    ResourceModel,
)
from stitch.api.db.model.oil_gas_field_source_value import value_attr_for
from stitch.api.entities import OGFieldQueryParams
from stitch.ogsi.model.types import OGSISrcKey

Q_FIELDS: Final[tuple[str, ...]] = (
    "name",
    "name_local",
    "basin",
    "state_province",
    "region",
)

EXACT_MATCH_FIELDS: Final[tuple[str, ...]] = (
    *Q_FIELDS,
    "country",
    "field_status",
    "location_type",
    "production_conventionality",
    "primary_hydrocarbon_group",
)

_HEADER_SORT_FIELDS: Final[frozenset[str]] = frozenset({"id", "source", "resource_id"})


def _filter_values(params: OGFieldQueryParams, field_name: str) -> list[Any]:
    value = getattr(params, field_name, None)
    if value is None:
        return []
    return list(value) if isinstance(value, list) else [value]


def _participating_columns(params: OGFieldQueryParams) -> list[str]:
    participating: list[str] = []
    if params.sort_by not in _HEADER_SORT_FIELDS:
        participating.append(params.sort_by)

    for field in EXACT_MATCH_FIELDS:
        if _filter_values(params, field):
            participating.append(field)

    if params.q:
        participating += Q_FIELDS

    return list(dict.fromkeys(participating))


def _override_join(resource_id: Any) -> ColumnElement[bool]:
    m = MembershipModel
    v = OilGasFieldSourceValueModel
    o = OGFieldResourceSourcePriority
    return and_(
        o.resource_id == resource_id,
        o.source_pk == m.source_pk,
        o.source == m.source,
        o.colname == v.colname,
    )


def construct_base_query_statement(
    licensed_sources: Collection[OGSISrcKey] | None = None,
    resource_ids: Collection[int] | None = None,
) -> CTE:
    s = OilGasFieldSourceModel
    v = OilGasFieldSourceValueModel
    m = MembershipModel
    r = ResourceModel
    p = OGFieldSourcePriority
    o = OGFieldResourceSourcePriority

    active_src = (
        select(
            r.id.label("resource_id"),
            m.source.label("source"),
            m.source_pk.label("source_pk"),
            o.priority.label("override_priority"),
            p.priority.label("default_priority"),
            v.colname.label("colname"),
            v.value_text,
            v.value_num,
            v.value_json,
        )
        .select_from(m)
        .join(r, r.id == m.resource_id)
        .join(p, p.source == m.source)
        .join(s, and_(s.id == m.source_pk, s.source == m.source))
        .join(v, v.source_pk == m.source_pk)
        .outerjoin(o, _override_join(r.id))
        .where(
            r.repointed_id.is_(None),
            m.status == MembershipStatus.ACTIVE,
        )
    )
    if licensed_sources is not None:
        active_src = active_src.where(
            m.source.in_(list(dict.fromkeys(licensed_sources)))
        )
    if resource_ids is not None:
        active_src = active_src.where(
            m.resource_id.in_(list(dict.fromkeys(resource_ids)))
        )
    return active_src.cte("active_src")


def base_source_query(
    params: OGFieldQueryParams,
    licensed_sources: Collection[OGSISrcKey] | None = None,
) -> Select[tuple[int]]:
    involved = _participating_columns(params)
    base_cte = construct_base_query_statement(licensed_sources)
    pivot = select(base_cte.c.source_pk, base_cte.c.source).group_by(
        base_cte.c.source_pk, base_cte.c.source
    )
    pivot = _add_pivot_columns(
        pivot,
        involved,
        base_cte.c.colname,
        lambda fn: getattr(base_cte.c, value_attr_for(fn)),
    )
    pivot_cte = pivot.cte("source_base")
    stmt = select(pivot_cte.c.source_pk)
    for cond in _build_field_conditions(pivot_cte, params):
        stmt = stmt.where(cond)
    stmt = stmt.where(pivot_cte.c.source.in_(list(dict.fromkeys(params.source))))
    if params.id is not None:
        stmt = stmt.where(pivot_cte.c.source_pk == params.id)
    return stmt.order_by(*_build_sort_clauses(pivot_cte, params, "source_pk"))


def _ranked(base_cte: CTE) -> CTE:
    cols = base_cte.c
    return (
        select(base_cte)
        .add_columns(
            func.row_number()
            .over(
                partition_by=(cols.resource_id, cols.colname),
                order_by=(
                    cols.override_priority.asc().nulls_last(),
                    cols.default_priority.asc(),
                    cols.source.asc(),
                    cols.source_pk.asc(),
                ),
            )
            .label("rn")
        )
        .cte()
    )


def add_ranking(base_cte: CTE) -> Select[tuple[Any, ...]]:
    ranked = _ranked(base_cte)
    return select(ranked).where(ranked.c.rn == 1)


def coalesced_winner_rows(
    resource_ids: Collection[int],
    licensed_sources: Collection[OGSISrcKey] | None = None,
) -> Select[tuple[Any, ...]]:
    base = construct_base_query_statement(licensed_sources, resource_ids=resource_ids)
    winners = add_ranking(base).cte("coalesced_winners")
    return select(
        winners.c.resource_id,
        winners.c.colname,
        winners.c.value_text,
        winners.c.value_num,
        winners.c.value_json,
        winners.c.source,
        winners.c.source_pk,
    )


def field_source_candidates(
    resource_id: int,
    field: str,
    licensed_sources: Collection[OGSISrcKey] | None = None,
) -> Select[tuple[Any, ...]]:
    base = construct_base_query_statement(licensed_sources, resource_ids=[resource_id])
    ranked = _ranked(base)
    c = ranked.c
    return (
        select(
            c.source,
            c.source_pk,
            c.value_text,
            c.value_num,
            c.value_json,
            c.override_priority.is_not(None).label("is_override"),
        )
        .where(c.colname == field)
        .order_by(c.rn)
    )


def coalesced_candidate_rows(
    resource_ids: Collection[int],
    licensed_sources: Collection[OGSISrcKey] | None = None,
) -> Select[tuple[Any, ...]]:
    base = construct_base_query_statement(licensed_sources, resource_ids=resource_ids)
    ranked = _ranked(base)
    s = OilGasFieldSourceModel
    return (
        select(
            ranked.c.resource_id,
            ranked.c.colname,
            ranked.c.value_text,
            ranked.c.value_num,
            ranked.c.value_json,
            ranked.c.source,
            ranked.c.source_pk,
            ranked.c.rn,
            s.source_record,
        )
        .join(s, s.id == ranked.c.source_pk)
        .order_by(
            ranked.c.default_priority,
            ranked.c.source,
            ranked.c.source_pk,
            ranked.c.colname,
        )
    )


def resource_universe() -> Select[tuple[int]]:
    m = MembershipModel
    r = ResourceModel
    return (
        select(r.id.label("resource_id"))
        .select_from(r)
        .join(m, m.resource_id == r.id)
        .where(r.repointed_id.is_(None), m.status == MembershipStatus.ACTIVE)
        .distinct()
    )


def resource_state_query(
    params: OGFieldQueryParams, permission_mask: int
) -> Select[tuple[int]]:
    state = OGFieldResourceState
    profile = _resource_state_profile(permission_mask)
    stmt = select(state.resource_id).where(state.permission_mask == permission_mask)
    for cond in _build_field_conditions(profile, params):
        stmt = stmt.where(cond)
    if params.id is not None:
        stmt = stmt.where(state.resource_id == params.id)
    return stmt.order_by(*_build_sort_clauses(profile, params, "resource_id"))


def resource_state_page_query(
    params: OGFieldQueryParams, permission_mask: int
) -> Select[Any]:
    state = OGFieldResourceState
    page = (
        resource_state_query(params, permission_mask)
        .limit(params.limit)
        .offset(params.offset)
        .subquery("page")
    )
    profile = _resource_state_profile(permission_mask)
    return profile.join(page, page.c.resource_id == state.resource_id).order_by(
        *_build_sort_clauses(profile, params, "resource_id")
    )


def _resource_state_profile(permission_mask: int) -> Select[Any]:
    state = OGFieldResourceState
    return select(state.__table__).where(state.permission_mask == permission_mask)


def resource_state_filter_option_query(
    field_name: str, permission_mask: int
) -> Select[tuple[str]]:
    state = OGFieldResourceState
    col = getattr(state, field_name)
    return (
        select(col)
        .where(state.permission_mask == permission_mask, col.is_not(None))
        .distinct()
        .order_by(col)
    )


def _add_pivot_columns(
    stmt: Select,
    fields: Collection[str],
    colname_col: ColumnElement[Any],
    value_col_for: Callable[[str], ColumnElement[Any]],
) -> Select:
    for field_name in fields:
        stmt = stmt.add_columns(
            func.max(
                case((colname_col == field_name, value_col_for(field_name)))
            ).label(field_name)
        )
    return stmt


def _require_column(cte: CTE | Select, field_name: str) -> ColumnElement[Any]:
    obj = cte.c if isinstance(cte, CTE) else cte.selected_columns
    col = getattr(obj, field_name, None)
    if col is None:
        raise RuntimeError(
            f"source query references {field_name!r}, absent from the narrowed "
            "pivot; participating-columns narrowing is out of sync."
        )
    return col


def _build_field_conditions(
    cte: CTE | Select,
    params: OGFieldQueryParams,
) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []

    if params.q:
        q_term = f"%{params.q}%"
        conditions.append(
            or_(*(_require_column(cte, field).ilike(q_term) for field in Q_FIELDS))
        )

    for field_name in EXACT_MATCH_FIELDS:
        values = _filter_values(params, field_name)
        if not values:
            continue
        conditions.append(_require_column(cte, field_name).in_(values))

    return conditions


def _build_sort_clauses(
    cte: CTE | Select,
    params: OGFieldQueryParams,
    default: Literal["resource_id", "source_pk"] = "source_pk",
) -> list[Any]:
    direction = desc if params.sort_order == "desc" else asc
    sort_by = default if params.sort_by in {"id", "resource_id"} else params.sort_by
    sort_col = _require_column(cte, sort_by)

    if sort_by == default:
        return [direction(sort_col).nulls_last()]

    return [
        direction(sort_col).nulls_last(),
        asc(_require_column(cte, default)),
    ]
