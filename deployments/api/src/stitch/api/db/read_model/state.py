
from __future__ import annotations

import logging
from collections.abc import Collection
from typing import Any, Final

from sqlalchemy import Select, delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from stitch.api.observability.context import named_query

from ..model import OGFieldResourceState, ResourceModel
from ..model.oil_gas_field_source_value import ATTRIBUTE_NAMES, materialize_value
from ..queries import coalesced_winner_rows, resource_universe
from .permissions import PERMISSION_MASKS, visible_sources_for_mask

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE: Final[int] = 500


def lock_resources_statement(resource_ids: Collection[int]) -> Select[tuple[int]]:
    return (
        select(ResourceModel.id)
        .where(ResourceModel.id.in_(sorted(set(resource_ids))))
        .order_by(ResourceModel.id)
        .with_for_update(key_share=True)
    )


async def lock_resources(session: AsyncSession, resource_ids: Collection[int]) -> None:
    if resource_ids:
        await session.execute(lock_resources_statement(resource_ids))


def _empty_state_row(resource_id: int, mask: int) -> dict[str, Any]:
    return {
        "resource_id": resource_id,
        "permission_mask": mask,
        **{field: None for field in ATTRIBUTE_NAMES},
        "provenance": {field: None for field in ATTRIBUTE_NAMES},
    }


async def _compute_state_rows(
    session: AsyncSession, resource_ids: list[int]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for mask in PERMISSION_MASKS:
        by_id = {rid: _empty_state_row(rid, mask) for rid in resource_ids}
        winners = await session.execute(
            coalesced_winner_rows(resource_ids, visible_sources_for_mask(mask))
        )
        for rid, colname, value_text, value_num, value_json, source, _ in winners:
            row = by_id[rid]
            row[colname] = materialize_value(
                colname,
                value_text=value_text,
                value_num=value_num,
                value_json=value_json,
            )
            row["provenance"][colname] = source
        rows.extend(by_id.values())
    return rows


async def refresh_resource_states(
    session: AsyncSession, resource_ids: Collection[int]
) -> list[int]:
    ids = sorted(set(resource_ids))
    if not ids:
        return []
    with named_query("read_model.refresh"):
        await lock_resources(session, ids)
        await session.execute(
            delete(OGFieldResourceState).where(
                OGFieldResourceState.resource_id.in_(ids)
            )
        )
        listable = sorted(
            (
                await session.scalars(
                    resource_universe().where(ResourceModel.id.in_(ids))
                )
            ).all()
        )
        if listable:
            await session.execute(
                insert(OGFieldResourceState),
                await _compute_state_rows(session, listable),
            )
    return listable


async def refresh_resource_state(session: AsyncSession, resource_id: int) -> None:
    await refresh_resource_states(session, [resource_id])


async def _delete_unlistable_state(session: AsyncSession) -> None:
    universe = resource_universe().subquery()
    await session.execute(
        delete(OGFieldResourceState).where(
            OGFieldResourceState.resource_id.not_in(select(universe.c.resource_id))
        )
    )


async def rebuild_all_resource_state(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> int:
    if batch_size < 1:
        raise ValueError(f"batch_size must be at least 1, got {batch_size}")

    async with session_factory() as session:
        pending = list(
            (
                await session.scalars(resource_universe().order_by(ResourceModel.id))
            ).all()
        )
    for start in range(0, len(pending), batch_size):
        async with session_factory.begin() as session:
            await refresh_resource_states(session, pending[start : start + batch_size])
        logger.info(
            "Rebuilt resource state for %d of %d resources.",
            min(start + batch_size, len(pending)),
            len(pending),
        )
    async with session_factory.begin() as session:
        await _delete_unlistable_state(session)
    return len(pending)
