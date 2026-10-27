from collections.abc import Collection, Sequence
from typing import Any, get_args

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.status import HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND

from stitch.api.db.errors import (
    InvalidActionError,
    ResourceIntegrityError,
    ResourceNotFoundError,
)
from stitch.api.auth import CurrentUser
from stitch.api.observability.context import named_query
from stitch.api.entities import (
    FILTER_OPTION_FIELDS,
    OGFieldQueryParams,
)
from stitch.api.db.og_field_source_actions import (
    attach_sources_to_resource,
    get_or_create_sources,
)
from stitch.ogsi.model import (
    OGFieldListItemView,
    OGFieldResource,
    OGFieldSourceValueView,
)
from stitch.ogsi.model.og_field import OilGasFieldBase
from stitch.ogsi.model.types import OGSISrcKey

from .model import (
    MembershipModel,
    MembershipStatus,
    OGFieldResourceSourcePriority,
    ResourceModel,
)
from .model.oil_gas_field_source_value import (
    ATTRIBUTE_NAMES,
    materialize_value,
)
from .queries import (
    field_source_candidates,
    resource_state_filter_option_query,
    resource_state_page_query,
    resource_state_query,
)
from .read_model.permissions import PUBLIC_SOURCES, read_model_mask
from .read_model.state import (
    lock_resources,
    refresh_resource_state,
    refresh_resource_states,
)
from .utils import (
    resource_model_to_entity,
)


_ALL_SOURCES: frozenset[OGSISrcKey] = frozenset(get_args(OGSISrcKey))


def _profile_mask(licensed_sources: Collection[OGSISrcKey] | None) -> int:
    if licensed_sources is None:
        licensed_sources = _ALL_SOURCES
    mask = read_model_mask(licensed_sources)
    if mask is not None:
        return mask
    if missing := sorted(PUBLIC_SOURCES - frozenset(licensed_sources)):
        reason = f"it is missing read access to public source(s) {missing}"
    else:
        reason = "it holds read access to a source the list can't serve yet"
    raise HTTPException(
        status_code=HTTP_403_FORBIDDEN,
        detail=f"This account can't list oil & gas fields: {reason}. "
        "Ask an administrator to update its source permissions.",
    )


async def query(
    session: AsyncSession,
    params: OGFieldQueryParams,
    licensed_sources: Collection[OGSISrcKey] | None = None,
) -> tuple[list[OGFieldListItemView], int]:
    if params.sort_by == "source":
        raise HTTPException(
            status_code=422,
            detail="sort_by=source is not supported for resource list queries.",
        )
    mask = _profile_mask(licensed_sources)

    count_stmt = select(func.count()).select_from(
        resource_state_query(params, mask).order_by(None).subquery()
    )
    with named_query("resources.count"):
        total = (await session.scalar(count_stmt)) or 0
    with named_query("resources.list_page"):
        rows = (await session.execute(resource_state_page_query(params, mask))).all()
    return [_state_row_to_list_item_view(row) for row in rows], total


def _state_row_to_list_item_view(row: Any) -> OGFieldListItemView:
    return OGFieldListItemView(
        id=row.resource_id,
        data=OilGasFieldBase(
            **{field: getattr(row, field) for field in ATTRIBUTE_NAMES}
        ),
        provenance={field: row.provenance.get(field) for field in ATTRIBUTE_NAMES},
    )


async def filter_options(
    session: AsyncSession,
    licensed_sources: Collection[OGSISrcKey] | None = None,
) -> dict[str, list[str]]:
    mask = _profile_mask(licensed_sources)
    options: dict[str, list[str]] = {}
    with named_query("resources.filter_options"):
        for field in FILTER_OPTION_FIELDS:
            stmt = resource_state_filter_option_query(field, mask)
            options[field] = list((await session.scalars(stmt)).all())
    return options


async def get(
    session: AsyncSession,
    id: int,
    licensed_sources: Collection[OGSISrcKey] | None = None,
) -> OGFieldResource:
    with named_query("resources.detail"):
        stmt = (
            select(ResourceModel)
            .options(selectinload(ResourceModel.memberships))
            .where(ResourceModel.id == id)
        )
        model = await session.scalar(stmt)
        if model is None:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"No Resource with id `{id}` found.",
            )
        await session.refresh(model, ["memberships"])
        return await resource_model_to_entity(
            session, model, licensed_sources=licensed_sources
        )


async def resolve_root_id(session: AsyncSession, id: int) -> int:
    with named_query("resources.resolve_root"):
        model = await session.scalar(
            select(ResourceModel).where(ResourceModel.id == id)
        )
        if model is None:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"No Resource with id `{id}` found.",
            )
        if model.repointed_id is None:
            return id
        try:
            return (await model.get_root(session)).id
        except ResourceNotFoundError as exc:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=(
                    f"Resource `{id}` could not be resolved to a current resource."
                ),
            ) from exc


async def get_resolved(
    session: AsyncSession,
    id: int,
    licensed_sources: Collection[OGSISrcKey] | None = None,
) -> OGFieldResource:
    root_id = await resolve_root_id(session, id)
    return await get(session, root_id, licensed_sources=licensed_sources)


async def field_source_values(
    session: AsyncSession,
    id: int,
    field: str,
    licensed_sources: Collection[OGSISrcKey] | None = None,
) -> list[OGFieldSourceValueView]:
    if field not in ATTRIBUTE_NAMES:
        raise HTTPException(
            status_code=422,
            detail=f"field={field} is not a known resource field.",
        )
    root_id = await resolve_root_id(session, id)

    with named_query("resources.field_source_values"):
        rows = (
            await session.execute(
                field_source_candidates(root_id, field, licensed_sources)
            )
        ).all()
    return [
        OGFieldSourceValueView(
            source=row.source,
            source_id=row.source_pk,
            value=materialize_value(
                field,
                value_text=row.value_text,
                value_num=row.value_num,
                value_json=row.value_json,
            ),
            priority=rank,
            is_override=bool(row.is_override),
        )
        for rank, row in enumerate(rows)
    ]


async def set_field_source_priority(
    session: AsyncSession,
    user: CurrentUser,
    id: int,
    field: str,
    ordered_source_pks: Sequence[int],
    licensed_sources: Collection[OGSISrcKey] | None = None,
) -> list[OGFieldSourceValueView]:
    if field not in ATTRIBUTE_NAMES:
        raise HTTPException(
            status_code=422,
            detail=f"field={field} is not a known resource field.",
        )
    with named_query("resources.set_field_source_priority.load"):
        await lock_resources(session, [id])
        resource = await session.get(ResourceModel, id, populate_existing=True)
    if resource is None:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND, detail=f"No Resource with id `{id}` found."
        )
    if resource.repointed_id is not None:
        raise ResourceIntegrityError(
            f"Cannot re-prioritize sources of repointed resource `{id}`."
        )
    if len(set(ordered_source_pks)) != len(ordered_source_pks):
        raise InvalidActionError("ordered_source_pks contains duplicate ids.")

    if licensed_sources is not None and set(licensed_sources) != _ALL_SOURCES:
        raise InvalidActionError(
            "You must have read permissions for all sources to reorder a field's "
            "sources."
        )

    with named_query("resources.set_field_source_priority.candidates"):
        rows = (
            await session.execute(field_source_candidates(id, field, licensed_sources))
        ).all()
    current_order = [row.source_pk for row in rows]
    eligible = set(current_order)
    requested = set(ordered_source_pks)
    if requested != eligible:
        raise InvalidActionError(
            "ordered_source_pks must cover exactly the sources with a value for "
            f"field {field!r} (missing={sorted(eligible - requested)}, "
            f"unexpected={sorted(requested - eligible)})."
        )

    if list(ordered_source_pks) == current_order:
        return await field_source_values(session, id, field, licensed_sources)

    source_by_pk = {row.source_pk: row.source for row in rows}
    with named_query("resources.set_field_source_priority.persist"):
        await session.execute(
            delete(OGFieldResourceSourcePriority).where(
                OGFieldResourceSourcePriority.resource_id == id,
                OGFieldResourceSourcePriority.colname == field,
            )
        )
        for priority, source_pk in enumerate(ordered_source_pks):
            session.add(
                OGFieldResourceSourcePriority.create(
                    created_by=user,
                    resource_id=id,
                    source=source_by_pk[source_pk],
                    source_pk=source_pk,
                    colname=field,
                    priority=priority,
                )
            )
        await session.flush()
        await refresh_resource_state(session, id)
    return await field_source_values(session, id, field, licensed_sources)


async def create(
    session: AsyncSession, user: CurrentUser, resource: OGFieldResource
) -> OGFieldResource:
    if resource.repointed_to is not None:
        raise ResourceIntegrityError(
            f"Cannot create resource that has been repointed.\n\tNew: {repr(resource)}"
        )
    with named_query("resources.create"):
        model = ResourceModel.create(created_by=user)
        session.add(model)
        await session.flush()
        if resource.source_data:
            src_models = await get_or_create_sources(
                session, user, resource.source_data
            )
            res = await attach_sources_to_resource(
                session=session, resource_id=model.id, source_rows=src_models, user=user
            )
            return res
        await session.refresh(model, ["memberships"])
        return await resource_model_to_entity(session, model)


async def apply_resource_merge(
    session: AsyncSession,
    user: CurrentUser,
    resource_ids: Sequence[int],
) -> OGFieldResource:
    unique_ids = list(dict.fromkeys(resource_ids))
    if len(unique_ids) < 2:
        raise InvalidActionError(
            f"Merging only possible between multiple ids: received: {unique_ids}"
        )

    stmt = (
        select(ResourceModel)
        .where(ResourceModel.id.in_(unique_ids))
        .execution_options(populate_existing=True)
    )

    with named_query("resources.merge.load"):
        await lock_resources(session, unique_ids)
        results = (await session.scalars(stmt)).all()
    missing_ids = set(unique_ids).difference(set([r.id for r in results]))
    if len(missing_ids) > 0:
        msg = f"Resources not found for ids: [{','.join(map(str, missing_ids))}]"
        raise ResourceNotFoundError(msg)

    if len(repointed := [r for r in results if r.repointed_id is not None]) > 0:
        moved = ", ".join(
            f"resource {r.id} is now resource {r.repointed_id}" for r in repointed
        )
        raise ResourceIntegrityError(
            f"Cannot merge any resource that has already been merged: {moved}."
        )

    with named_query("resources.merge.apply"):
        new_resource = ResourceModel.create(created_by=user)
        session.add(new_resource)
        await session.flush()

        for res in results:
            res.repointed_id = new_resource.id

        _ = await _repoint_memberships(session, user, new_resource.id, unique_ids)

        await refresh_resource_states(session, [*unique_ids, new_resource.id])

        await session.refresh(new_resource, ["memberships"])
        return await resource_model_to_entity(session, new_resource)


async def _repoint_memberships(
    session: AsyncSession,
    user: CurrentUser,
    to_id: int,
    from_ids: Sequence[int],
) -> Sequence[MembershipModel]:
    res = await session.get(ResourceModel, to_id)
    if res is None:
        raise ResourceNotFoundError(f"No resource found for id = {to_id}.")

    existing_memberships = (
        await session.scalars(
            select(MembershipModel)
            .where(MembershipModel.resource_id.in_(from_ids))
            .order_by(MembershipModel.id)
        )
    ).all()

    new_by_source_pk: dict[int, MembershipModel] = {}
    for mem in existing_memberships:
        new_mem = new_by_source_pk.get(mem.source_pk)
        if new_mem is None:
            new_by_source_pk[mem.source_pk] = MembershipModel.create(
                created_by=user,
                resource_id=res.id,
                source=mem.source,
                source_pk=mem.source_pk,
                status=mem.status,
            )
        elif mem.status == MembershipStatus.ACTIVE:
            new_mem.status = MembershipStatus.ACTIVE
        if mem.status == MembershipStatus.ACTIVE:
            mem.status = MembershipStatus.INACTIVE
    new_memberships = list(new_by_source_pk.values())
    session.add_all(new_memberships)
    return new_memberships
