from sqlalchemy import select, and_, func, Select
from sqlalchemy.ext.asyncio import AsyncSession
from collections import Counter
from stitch.api.db.queries import construct_base_query_statement
from stitch.api.db.model import (
    OilGasFieldSourceModel,
    OilGasFieldSourceValueModel,
    MembershipModel,
    OGFieldSourcePriority,
    OGFieldResourceSourcePriority,
    ResourceModel,
    MembershipStatus,
    MergeCandidateItemModel,
    MergeCandidateModel,
)
from stitch.api.entities import MergeCandidateStatus
from .helpers import prepare
from .matching import (
    build_groups,
    exact_edges,
    similarity_edges,
    split_by_confidence,
)
from .model import OilGasFieldMatchRecord


def get_merge_suggestion_exclusions_sel() -> Select[tuple[int]]:
    mci = MergeCandidateItemModel
    mcm = MergeCandidateModel
    res = ResourceModel
    return (
        select(
            mci.resource_id.distinct(),
        )
        .select_from(mci)
        .join(mcm, mcm.id == mci.merge_candidate_id)
        .join(res, res.id == mci.resource_id)
        .where(
            res.repointed_id.is_(None),
            mcm.status.in_([MergeCandidateStatus.PENDING, MergeCandidateStatus.DENIED]),
        )
    )


async def load_coalesced_records(
    session: AsyncSession,
) -> tuple[OilGasFieldMatchRecord, ...]:
    m = MembershipModel
    v = OilGasFieldSourceValueModel
    p = OGFieldSourcePriority
    o = OGFieldResourceSourcePriority

    ex_stmt = get_merge_suggestion_exclusions_sel()
    excluded = (await session.scalars(ex_stmt)).all()
    base = (
        select(
            m.resource_id.label("id"),
            v.colname.label("colname"),
            v.value_text,
            v.value_num,
            v.value_json,
        )
        .select_from(m)
        .distinct(
            m.resource_id, v.colname
        )  # produces distinct on for Postgresql, with orderby, we get same as the ROW NUMBER window function
        .join(v, v.source_pk == m.source_pk)
        .join(p, p.source == m.source)
        .outerjoin(
            o,
            and_(
                o.resource_id == m.resource_id,
                o.source_pk == m.source_pk,
                o.source == m.source,
                o.colname == v.colname,
            ),
        )
        .where(m.status == MembershipStatus.ACTIVE, m.resource_id.not_in(excluded))
        .order_by(m.resource_id, v.colname, o.priority, p.priority)
    )
    result = await session.execute(base)
    res = {}
    for row in result.all():
        id_, col, vt, vn, vj = row._tuple()
        val = next(filter(lambda x: x is not None, (vt, vn, vj)))
        if id_ not in res:
            res[id_] = []
        res[id_].append((col, val))

    return tuple(
        [OilGasFieldMatchRecord(**{c: v for item in res.values() for c, v in item})]
    )


async def generate_merge_candidate_suggestions(
    session: AsyncSession,
) -> tuple[tuple[int, int], ...]:
    # get all coalesced resources into dataframe
    records = await load_coalesced_records(session)

    prepared = prepare(records)

    exact, _ = exact_edges(prepared)
    edges = exact + similarity_edges(prepared)

    groups, _ = build_groups(prepared, edges, 2)
    groups, _ = split_by_confidence(groups, min_confidence="medium")

    return tuple((g.resource_ids[0], g.resource_ids[1]) for g in groups)
