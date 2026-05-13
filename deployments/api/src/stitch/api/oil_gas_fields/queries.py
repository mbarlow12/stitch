from collections.abc import Collection
from typing import Any

from sqlalchemy import (
    ColumnElement,
    String,
    and_,
    asc,
    case,
    cast,
    desc,
    func,
    or_,
    select,
)

from stitch.api.oil_gas_fields.entities import OGFieldQueryParams
from stitch.ogsi.model.og_field import OilGasFieldBase
from stitch.ogsi.model.types import OGSISrcKey

from .model import (
    OilGasFieldMembershipModel,
    MembershipStatus,
    OilGasFieldSourcePriorityModel,
    OilGasFieldSourceModel,
    OilGasFieldResourceModel,
)
from .model.source_priority import DEFAULT_PRIORITIES


_LIST_JSON_FIELDS = ("owners", "operators")
_LIST_SCALAR_FIELDS = tuple(
    field_name
    for field_name in OilGasFieldBase.model_fields
    if field_name not in _LIST_JSON_FIELDS
)
_LIST_DATA_FIELDS = (*_LIST_SCALAR_FIELDS, *_LIST_JSON_FIELDS)
PROVENANCE_SUFFIX = "__provenance_source"


def _priority_values() -> tuple[int, ...]:
    return tuple(int(priority["priority"]) for priority in DEFAULT_PRIORITIES)


def build_redacted_query(
    params: OGFieldQueryParams, licensed_sources: Collection[OGSISrcKey]
):
    coalesced = build_redacted_resource_list_cte(params, licensed_sources)
    filtered = select(coalesced)
    for condition in _build_final_conditions(coalesced, params):
        filtered = filtered.where(condition)

    total_stmt = select(func.count()).select_from(filtered.subquery())

    page_stmt = (
        filtered.order_by(*_build_sort_clauses(coalesced, params))
        .offset(params.offset)
        .limit(params.limit)
    )
    return total_stmt, page_stmt


def build_redacted_resource_list_cte(
    params: OGFieldQueryParams,
    licensed_sources: Collection[OGSISrcKey],
):
    s = OilGasFieldSourceModel
    m = OilGasFieldMembershipModel
    r = OilGasFieldResourceModel
    p = OilGasFieldSourcePriorityModel

    selected_sources = list(dict.fromkeys(params.source))
    licensed = list(dict.fromkeys(licensed_sources))
    source_join_conditions = [
        s.id == m.source_pk,
        s.source == m.source,
    ]
    if licensed:
        source_join_conditions.append(s.source.in_(licensed))

    qualified = (
        select(
            r.id.label("id"),
            m.source.label("source"),
            p.priority.label("priority"),
        )
        .join(m, m.resource_id == r.id)
        .join(p, p.source == m.source)
        .outerjoin(s, and_(*source_join_conditions))
        .where(
            r.repointed_id.is_(None),
            m.status == MembershipStatus.ACTIVE,
            m.source.in_(selected_sources),
        )
    )

    for field_name in _LIST_DATA_FIELDS:
        qualified = qualified.add_columns(getattr(s, field_name).label(field_name))

    qualified_cte = qualified.cte("qualified_resource_sources")
    coalesced = select(qualified_cte.c.id.label("id")).group_by(qualified_cte.c.id)

    for field_name in _LIST_SCALAR_FIELDS:
        field_col = getattr(qualified_cte.c, field_name)
        value_by_priority = [
            func.max(case((qualified_cte.c.priority == priority, field_col)))
            for priority in _priority_values()
        ]
        provenance_by_priority = [
            func.max(
                case(
                    (
                        and_(
                            qualified_cte.c.priority == priority,
                            field_col.is_not(None),
                        ),
                        qualified_cte.c.source,
                    )
                )
            )
            for priority in _priority_values()
        ]
        coalesced = coalesced.add_columns(
            func.coalesce(*value_by_priority).label(field_name),
            func.coalesce(*provenance_by_priority).label(
                f"{field_name}{PROVENANCE_SUFFIX}"
            ),
        )

    for field_name in _LIST_JSON_FIELDS:
        value_alias = qualified_cte.alias(f"{field_name}_value_source")
        provenance_alias = qualified_cte.alias(f"{field_name}_provenance_source")
        value_col = getattr(value_alias.c, field_name)
        provenance_col = getattr(provenance_alias.c, field_name)
        value_is_present = _json_value_is_present(value_col)
        provenance_is_present = _json_value_is_present(provenance_col)

        value_subquery = (
            select(value_col)
            .where(
                value_alias.c.id == qualified_cte.c.id,
                value_is_present,
            )
            .order_by(value_alias.c.priority.asc())
            .limit(1)
            .scalar_subquery()
        )
        provenance_subquery = (
            select(provenance_alias.c.source)
            .where(
                provenance_alias.c.id == qualified_cte.c.id,
                provenance_is_present,
            )
            .order_by(provenance_alias.c.priority.asc())
            .limit(1)
            .scalar_subquery()
        )
        coalesced = coalesced.add_columns(
            value_subquery.label(field_name),
            provenance_subquery.label(f"{field_name}{PROVENANCE_SUFFIX}"),
        )

    return coalesced.cte("redacted_resource_list")


def _json_value_is_present(col) -> ColumnElement[bool]:
    return and_(col.is_not(None), cast(col, String) != "null")


def _build_final_conditions(
    coalesced,
    params: OGFieldQueryParams,
) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []

    if params.q:
        q_term = f"%{params.q}%"
        q_conditions: list[ColumnElement[bool]] = []
        for field_name in OilGasFieldSourceModel._q_fields:
            col = getattr(coalesced.c, field_name, None)
            if col is not None:
                q_conditions.append(col.ilike(q_term))
        if q_conditions:
            conditions.append(or_(*q_conditions))

    for field_name in OilGasFieldSourceModel._exact_match_fields:
        value = getattr(params, field_name, None)
        if value is None:
            continue
        col = _resource_list_column(coalesced, field_name)
        if col is not None:
            conditions.append(col == value)

    return conditions


def _build_sort_clauses(coalesced, params: OGFieldQueryParams) -> list[Any]:
    sort_col = _resource_list_column(coalesced, params.sort_by)
    clauses: list[Any] = []
    if sort_col is not None:
        direction = desc if params.sort_order == "desc" else asc
        clauses.append(direction(sort_col).nulls_last())
    if params.sort_by not in {"id", "resource_id"}:
        clauses.append(asc(coalesced.c.id))
    return clauses


def _resource_list_column(coalesced, field_name: str):
    if field_name == "resource_id":
        return coalesced.c.id
    return getattr(coalesced.c, field_name, None)
