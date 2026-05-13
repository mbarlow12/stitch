import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from .entities import (
    OGFieldQueryParams,
    GenerateMergeCandidatesResponse,
    GenerateMergeCandidatesRequest,
    MergeCandidateView,
    MergeCandidateCreateRequest,
)
from .actions.resource import create, query, get
from .actions import merge_candidate as merge_actions
from .actions import source as og_field_source_actions

from stitch.api.entities import PaginatedResponse
from stitch.api.db.config import UnitOfWorkDep
from stitch.api.db.errors import (
    InvalidActionError,
    ResourceNotFoundError,
    ResourceIntegrityError,
)
from stitch.api.auth import CurrentUser
from stitch.api.db.utils import (
    resource_to_view,
    resource_to_detail_view,
)

from stitch.ogsi.model import (
    OGFieldDetailView,
    OGFieldListItemView,
    OGFieldResource,
    OGFieldView,
    OGFieldSource,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/oil-gas-fields",
    tags=["oil_gas_fields"],
    responses={404: {"description": "Not found"}},
)


@router.post("/", response_model=OGFieldResource)
async def create_resource(
    *, uow: UnitOfWorkDep, user: CurrentUser, resource_in: OGFieldResource
) -> OGFieldResource:
    return await create(session=uow.session, user=user, resource=resource_in)


@router.get("/")
async def get_all_resources(
    *,
    uow: UnitOfWorkDep,
    _user: CurrentUser,
    params: Annotated[OGFieldQueryParams, Query()],
) -> PaginatedResponse[OGFieldListItemView]:
    items, total_count = await query(session=uow.session, params=params)
    return PaginatedResponse(
        items=items,
        total_count=total_count,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/{id}", response_model=OGFieldView)
async def get_resource(
    *, uow: UnitOfWorkDep, user: CurrentUser, id: int
) -> OGFieldView:
    res: OGFieldResource = await get(session=uow.session, id=id)
    return resource_to_view(resource=res)


@router.get("/{id}/detail", response_model=OGFieldDetailView)
async def get_resource_detail(
    *, uow: UnitOfWorkDep, user: CurrentUser, id: int
) -> OGFieldDetailView:
    res: OGFieldResource = await get(session=uow.session, id=id)
    return resource_to_detail_view(resource=res)


@router.get("/{resource_id}/sources")
async def query_sources_by_resource_id(
    uow: UnitOfWorkDep,
    user: CurrentUser,
    resource_id: int,
    params: Annotated[OGFieldQueryParams, Query()],
) -> PaginatedResponse[OGFieldSource]:
    items, total_count = await og_field_source_actions.query(
        session=uow.session, params=params
    )
    return PaginatedResponse(
        items=list(items),
        total_count=total_count,
        page=params.page,
        page_size=params.page_size,
    )


# Sources


@router.get("/sources")
async def query_oil_gas_field_sources(
    uow: UnitOfWorkDep,
    user: CurrentUser,
    params: Annotated[OGFieldQueryParams, Query()],
) -> PaginatedResponse[OGFieldSource]:
    items, total_count = await og_field_source_actions.query(
        session=uow.session, params=params
    )
    return PaginatedResponse(
        items=list(items),
        total_count=total_count,
        page=params.page,
        page_size=params.page_size,
    )


@router.post("/sources", response_model=OGFieldSource)
async def create_oil_gas_field_source(
    source: OGFieldSource,
    uow: UnitOfWorkDep,
    user: CurrentUser,
) -> OGFieldSource:
    """Create and return a bare Oil & Gas Field Source. Does not create memberships or associated resource.

    Args:
        source: raw source data
        uow: unit of work (db transaction context)
        user: the logged in User

    Returns:
        The OGFieldSource_ object with created id
    """
    session = uow.session

    return await og_field_source_actions.create_source(
        session=session, user=user, source=source
    )


@router.post("/sources/bulk", response_model=Sequence[OGFieldSource])
def create_sources_bulk(
    sources: Sequence[OGFieldSource],
    uow: UnitOfWorkDep,
    user: CurrentUser,
) -> Sequence[OGFieldSource]: ...


@router.get("/sources/{id}", response_model=OGFieldSource)
async def get_oil_gas_field_source_by_id(
    id: int, uow: UnitOfWorkDep, user: CurrentUser
):
    return await og_field_source_actions.get_source(session=uow.session, id=id)


@router.get("/sources/{id}/detail", response_model=OGFieldSource)
async def get_oil_gas_field_source_detail_by_id(
    id: int, uow: UnitOfWorkDep, user: CurrentUser
):
    return await og_field_source_actions.get_source(session=uow.session, id=id)


# Merging


@router.post("/generate-merge-candidates")
async def generate_merge_candidates(
    *,
    gen_request: GenerateMergeCandidatesRequest,
    uow: UnitOfWorkDep,
    _user: CurrentUser,
) -> GenerateMergeCandidatesResponse:
    return await merge_actions.generate_merge_candidates(
        session=uow.session, user=_user, params=gen_request.params
    )


@router.get("/merge-candidates", response_model=list[MergeCandidateView])
async def list_merge_candidates(
    *, uow: UnitOfWorkDep, _user: CurrentUser
) -> list[MergeCandidateView]:
    return await merge_actions.list_merge_candidates(session=uow.session)


@router.get("/merge-candidates/{id}", response_model=MergeCandidateView)
async def get_merge_candidate(
    *, uow: UnitOfWorkDep, _user: CurrentUser, id: int
) -> MergeCandidateView:
    try:
        return await merge_actions.get_merge_candidate(
            session=uow.session,
            candidate_id=id,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/merge-candidates/{id}/preview", response_model=OGFieldMergePreviewView)
async def preview_merge_candidate(
    *,
    uow: UnitOfWorkDep,
    _user: CurrentUser,
    id: int,
) -> OGFieldMergePreviewView:
    try:
        return await merge_actions.preview_merge_candidate(
            session=uow.session,
            candidate_id=id,
        )
    except (InvalidActionError, ResourceIntegrityError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error while previewing merge candidate %s: %s", id, exc)
        raise HTTPException(
            status_code=500,
            detail="Internal error during merge candidate preview",
        )


@router.post("/merge-candidates", response_model=MergeCandidateView)
async def create_merge_candidate(
    *,
    uow: UnitOfWorkDep,
    user: CurrentUser,
    request: MergeCandidateCreateRequest,
) -> MergeCandidateView:
    logger.info(
        "Merge candidate requested by user=%s for resource_ids=%s",
        getattr(user, "sub", "<anon>"),
        request.resource_ids,
    )

    try:
        return await merge_actions.create_merge_candidate(
            session=uow.session,
            user=user,
            resource_ids=request.resource_ids,
        )
    except (InvalidActionError, ResourceIntegrityError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "Error while creating merge candidate for resource_ids %s: %s",
            request.resource_ids,
            exc,
        )
        raise HTTPException(
            status_code=500,
            detail="Internal error during merge candidate creation",
        )


@router.post("/merge-candidates/{id}/approve", response_model=MergeCandidateView)
async def approve_merge_candidate(
    *,
    uow: UnitOfWorkDep,
    user: CurrentUser,
    id: int,
    request: MergeCandidateReviewRequest | None = None,
) -> MergeCandidateView:
    try:
        return await merge_actions.approve_merge_candidate(
            session=uow.session,
            user=user,
            candidate_id=id,
            request=request,
        )
    except (InvalidActionError, ResourceIntegrityError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error while approving merge candidate %s: %s", id, exc)
        raise HTTPException(
            status_code=500,
            detail="Internal error during merge candidate approval",
        )


@router.post("/merge-candidates/{id}/deny", response_model=MergeCandidateView)
async def deny_merge_candidate(
    *,
    uow: UnitOfWorkDep,
    user: CurrentUser,
    id: int,
    request: MergeCandidateReviewRequest | None = None,
) -> MergeCandidateView:
    try:
        return await merge_actions.deny_merge_candidate(
            session=uow.session,
            user=user,
            candidate_id=id,
            request=request,
        )
    except (InvalidActionError, ResourceIntegrityError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error while denying merge candidate %s: %s", id, exc)
        raise HTTPException(
            status_code=500,
            detail="Internal error during merge candidate denial",
        )
