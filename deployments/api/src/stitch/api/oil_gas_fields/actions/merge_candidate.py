from __future__ import annotations
from pydantic import BaseModel
from collections import defaultdict

from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from stitch.api.auth import CurrentUser
from stitch.api.coalesce import coalesce_og_field_resource
from stitch.api.db.errors import (
    InvalidActionError,
    ResourceIntegrityError,
    ResourceNotFoundError,
)
from stitch.api.oil_gas_fields.entities import (
    MergeCandidateReviewRequest,
    MergeCandidateStatus,
    MergeCandidateView,
    OGFieldMergePreviewView,
)
from stitch.api.oil_gas_fields.entities.view import (
    MERGE_PENDING,
    MERGE_APPROVED,
    MERGE_DENIED,
)
from stitch.ogsi.model.og_field import OilGasFieldBase
from stitch.ogsi.model import OGFieldListItemView
from stitch.ogsi.model.types import OGSISrcKey

from stitch.api.oil_gas_fields.entities import (
    OGFieldQueryParams,
    GenerateMergeCandidatesResponse,
)
from stitch.api.oil_gas_fields.model import (
    MergeCandidateItemModel,
    MergeCandidateModel,
    OilGasFieldMembershipModel,
    MembershipStatus,
    OilGasFieldSourcePriorityModel,
    OilGasFieldSourceModel,
    OilGasFieldResourceModel,
)
from .resource import apply_resource_merge, get, query


class MatchGroup(BaseModel):
    ids: list[int]
    normalized_name: str
    country: str


def _normalize_name(name: str | None):
    if name is None:
        return None
    normalized = name.strip().casefold()
    return normalized


def _group_duplicate_names(
    items: list[OGFieldListItemView],
) -> dict[str, list[OGFieldListItemView]]:
    grouped: dict[str, list[OGFieldListItemView]] = defaultdict(list)
    for item in items:
        _nname = _normalize_name(item.data.name)
        if _nname is None:
            continue
        grouped[_nname].append(item)
    return {
        normalized_name: grouped_items
        for normalized_name, grouped_items in grouped.items()
        if len(grouped_items) > 1
    }


def _normalize_country(country: str | None) -> str | None:
    if country is None:
        return None
    normalized = country.strip().upper()
    return normalized or None


async def _resolve_match_groups(
    session: AsyncSession,
    duplicate_groups: dict[str, list[OGFieldListItemView]],
) -> tuple[list[MatchGroup], int]:
    match_groups: list[MatchGroup] = []
    detail_records_fetched = 0

    for normalized_name, candidates in duplicate_groups.items():
        by_country: dict[str, list[int]] = defaultdict(list)

        for candidate in candidates:
            detail = await get(session, candidate.id)
            detail_records_fetched += 1
            _country = detail.view.country if detail.view is not None else None
            normalized_country = _normalize_country(_country)
            if normalized_country is None:
                continue
            by_country[normalized_country].append(detail.id or -1)

        for country, ids in by_country.items():
            if len(ids) > 1:
                match_groups.append(
                    MatchGroup(
                        ids=sorted(ids),
                        normalized_name=normalized_name,
                        country=country,
                    )
                )

    return match_groups, detail_records_fetched


def _normalize_resource_ids(resource_ids: Sequence[int]) -> list[int]:
    unique_ids = list(dict.fromkeys(resource_ids))
    if len(unique_ids) < 2:
        raise InvalidActionError(
            f"Merging only possible between multiple ids: received: {unique_ids}"
        )
    return unique_ids


async def _load_mergeable_resources(
    session: AsyncSession, resource_ids: Sequence[int]
) -> Sequence[OilGasFieldResourceModel]:
    unique_ids = _normalize_resource_ids(resource_ids)
    stmt = select(OilGasFieldResourceModel).where(
        OilGasFieldResourceModel.id.in_(unique_ids)
    )
    results = (await session.scalars(stmt)).all()

    missing_ids = set(unique_ids).difference({r.id for r in results})
    if missing_ids:
        msg = (
            f"Resources not found for ids: [{','.join(map(str, sorted(missing_ids)))}]"
        )
        raise ResourceNotFoundError(msg)

    repointed = [r for r in results if r.repointed_id is not None]
    if repointed:
        reprs = map(repr, repointed)
        msg = f"Repointed: [{','.join(reprs)}]"
        raise ResourceIntegrityError(
            f"Cannot merge any resource that has already been merged. {msg}"
        )

    return results


def _fingerprint(resource_ids: Sequence[int]) -> str:
    return ":".join(map(str, sorted(set(resource_ids))))


def _candidate_to_view(model: MergeCandidateModel) -> MergeCandidateView:
    return MergeCandidateView(
        id=model.id,
        resource_ids=[
            item.resource_id for item in sorted(model.items, key=lambda i: i.position)
        ],
        status=model.status,
        review_notes=model.review_notes,
        merged_resource_id=model.merged_resource_id,
        created=model.created,
        updated=model.updated,
        created_by_id=model.created_by_id,
        last_updated_by_id=model.last_updated_by_id,
        reviewed_at=model.reviewed_at,
        reviewed_by_id=model.reviewed_by_id,
    )


async def _load_candidate_model(
    session: AsyncSession, candidate_id: int
) -> MergeCandidateModel:
    stmt = (
        select(MergeCandidateModel)
        .options(selectinload(MergeCandidateModel.items))
        .where(MergeCandidateModel.id == candidate_id)
    )
    model = await session.scalar(stmt)
    if model is None:
        raise ResourceNotFoundError(
            f"No merge candidate found for id = {candidate_id}."
        )
    return model


async def generate_merge_candidates(
    session: AsyncSession, user: CurrentUser, params: OGFieldQueryParams
) -> GenerateMergeCandidatesResponse:
    items, _ = await query(session, params)
    duplicate_groups = _group_duplicate_names(items)
    match_groups, detail_records_fetched = await _resolve_match_groups(
        session=session,
        duplicate_groups=duplicate_groups,
    )

    merge_results: list[dict] = []
    for group in match_groups:
        response = await create_merge_candidate(
            session=session, user=user, resource_ids=group.ids
        )
        merge_results.append(
            {
                "ids": group.ids,
                "response": response,
            }
        )
    return GenerateMergeCandidatesResponse(
        initiated_by=user.name or "",
        duplicate_name_candidate_count=sum(
            len(group) for group in duplicate_groups.values()
        ),
        detail_records_fetched=detail_records_fetched,
        match_groups=[group.ids for group in match_groups],
        merge_results=merge_results,
    )


async def list_merge_candidates(session: AsyncSession) -> list[MergeCandidateView]:
    stmt = (
        select(MergeCandidateModel)
        .options(selectinload(MergeCandidateModel.items))
        .order_by(MergeCandidateModel.created.desc())
    )
    candidates = (await session.scalars(stmt)).all()
    return [_candidate_to_view(candidate) for candidate in candidates]


async def get_merge_candidate(
    session: AsyncSession, candidate_id: int
) -> MergeCandidateView:
    candidate = await _load_candidate_model(session, candidate_id)
    return _candidate_to_view(candidate)


async def create_merge_candidate(
    session: AsyncSession,
    user: CurrentUser,
    resource_ids: list[int],
) -> MergeCandidateView:
    unique_ids = list(dict.fromkeys(resource_ids))
    await _load_mergeable_resources(session, unique_ids)

    fingerprint = _fingerprint(resource_ids)
    existing = await session.scalar(
        select(MergeCandidateModel)
        .options(selectinload(MergeCandidateModel.items))
        .where(MergeCandidateModel.fingerprint == fingerprint)
    )
    if existing is not None:
        if existing.status == MERGE_PENDING:
            raise InvalidActionError(
                f"A pending merge candidate already exists for resources {resource_ids}."
            )
        if existing.status == MERGE_DENIED:
            raise InvalidActionError(
                f"A denied merge candidate already exists for resources {resource_ids}."
            )
        raise InvalidActionError(
            f"An approved merge candidate already exists for resources {resource_ids}."
        )

    candidate = MergeCandidateModel.create(created_by=user, fingerprint=fingerprint)
    session.add(candidate)
    await session.flush()

    session.add_all(
        [
            MergeCandidateItemModel(
                merge_candidate_id=candidate.id,
                resource_id=resource_id,
                position=position,
            )
            for position, resource_id in enumerate(resource_ids)
        ]
    )
    await session.flush()
    await session.refresh(candidate, ["items"])
    return _candidate_to_view(candidate)


async def approve_merge_candidate(
    session: AsyncSession,
    user: CurrentUser,
    candidate_id: int,
    request: MergeCandidateReviewRequest | None = None,
) -> MergeCandidateView:
    candidate = await _load_candidate_model(session, candidate_id)
    if candidate.status != MERGE_PENDING:
        raise InvalidActionError(
            f"Merge candidate {candidate_id} is not pending; current status={candidate.status}."
        )

    resource_ids = [
        item.resource_id for item in sorted(candidate.items, key=lambda i: i.position)
    ]
    await _load_mergeable_resources(session, resource_ids)
    merged_resource = await apply_resource_merge(
        session=session,
        user=user,
        resource_ids=resource_ids,
    )

    candidate.status = MERGE_APPROVED
    candidate.review_notes = request.review_notes if request else None
    candidate.reviewed_at = datetime.now(timezone.utc)
    candidate.reviewed_by_id = user.id
    candidate.last_updated_by_id = user.id
    candidate.merged_resource_id = merged_resource.id
    await session.flush()

    candidate = await _load_candidate_model(session, candidate_id)
    return _candidate_to_view(candidate)


async def deny_merge_candidate(
    session: AsyncSession,
    user: CurrentUser,
    candidate_id: int,
    request: MergeCandidateReviewRequest | None = None,
) -> MergeCandidateView:
    candidate = await _load_candidate_model(session, candidate_id)
    if candidate.status != MERGE_PENDING:
        raise InvalidActionError(
            f"Merge candidate {candidate_id} is not pending; current status={candidate.status}."
        )

    candidate.status = MERGE_DENIED
    candidate.review_notes = request.review_notes if request else None
    candidate.reviewed_at = datetime.now(timezone.utc)
    candidate.reviewed_by_id = user.id
    candidate.last_updated_by_id = user.id
    await session.flush()
    candidate = await _load_candidate_model(session, candidate_id)
    return _candidate_to_view(candidate)


async def preview_merge_candidate(
    session: AsyncSession,
    candidate_id: int,
) -> OGFieldMergePreviewView:
    candidate = await _load_candidate_model(session, candidate_id)

    resource_ids = [
        item.resource_id for item in sorted(candidate.items, key=lambda i: i.position)
    ]

    await _load_mergeable_resources(session, resource_ids)

    stmt = (
        select(OilGasFieldSourceModel)
        .join(
            OilGasFieldMembershipModel,
            OilGasFieldMembershipModel.source_pk == OilGasFieldSourceModel.id,
        )
        .where(OilGasFieldMembershipModel.resource_id.in_(resource_ids))
        .where(OilGasFieldMembershipModel.status == MembershipStatus.ACTIVE)
    )
    source_models = (await session.scalars(stmt)).all()

    priorities = (
        await session.scalars(
            select(OilGasFieldSourcePriorityModel.source).order_by(
                OilGasFieldSourcePriorityModel.priority
            )
        )
    ).all()

    source_entities = [src.as_entity() for src in source_models]
    merged_data, raw_provenance = coalesce_og_field_resource(
        source_entities,
        priorities,
    )

    provenance: dict[str, OGSISrcKey | None] = {
        key: (None if value is None else value[1])
        for key, value in raw_provenance.items()
    }

    data = OilGasFieldBase(
        **{
            field_name: getattr(merged_data, field_name, None)
            for field_name in OilGasFieldBase.model_fields
        }
    )

    return OGFieldMergePreviewView(
        resource_ids=resource_ids,
        data=data,
        provenance=provenance,
    )
