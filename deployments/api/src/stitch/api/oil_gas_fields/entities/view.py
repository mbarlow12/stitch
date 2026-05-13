from datetime import datetime
from typing import Literal
from pydantic import BaseModel

from stitch.ogsi.model import OilGasFieldBase, OGSISrcKey

type MergeCandidateStatus = Literal["PENDING", "APPROVED", "DENIED"]
MERGE_PENDING: MergeCandidateStatus = "PENDING"
MERGE_APPROVED: MergeCandidateStatus = "APPROVED"
MERGE_DENIED: MergeCandidateStatus = "DENIED"


class MergeCandidateView(BaseModel):
    id: int
    resource_ids: list[int]
    status: MergeCandidateStatus
    review_notes: str | None = None
    merged_resource_id: int | None = None
    created: datetime
    updated: datetime
    created_by_id: int
    last_updated_by_id: int
    reviewed_at: datetime | None = None
    reviewed_by_id: int | None = None


class OGFieldMergePreviewView(BaseModel):
    resource_ids: list[int]
    data: OilGasFieldBase
    provenance: dict[str, OGSISrcKey | None]


class GenerateMergeCandidatesResponse(BaseModel):
    initiated_by: str
    duplicate_name_candidate_count: int
    detail_records_fetched: int
    match_groups: list[list[int]]
    merge_results: list[dict]
