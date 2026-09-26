"""Integration tests for the merge-candidate endpoints (real SQLite)."""

from collections.abc import Sequence
from unittest.mock import patch

from httpx import AsyncClient
import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from stitch.auth import TokenClaims
from stitch.auth.permissions import MERGE_CANDIDATE_CREATE, SOURCE_READ_GEM

from tests.factories import ResourceCreateFactory
from stitch.api.auth import get_token_claims
from stitch.api.db import link_actions
from stitch.api.db.config import UnitOfWork
from stitch.api.db.model import MembershipModel, OGFieldResourceSourcePriority
from stitch.api.main import app
from stitch.ogsi.model import OGFieldResource, OGFieldSource


async def _create_resource(
    client: AsyncClient, fact: ResourceCreateFactory, name: str
) -> int:
    payload = fact(name=name).model_dump(mode="json")
    resp = await client.post("/oil-gas-fields/", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def _create_resource_with_sources(
    client: AsyncClient,
    res_factory,
    sources: Sequence[OGFieldSource],
) -> int:
    """POST a resource built from explicit source entities (controlled values)."""
    model: OGFieldResource = res_factory.build(
        id=None,
        source_data=list(sources),
        constituents=frozenset(),
        repointed_to=None,
        view=None,
        provenance={},
    )
    resp = await client.post("/oil-gas-fields/", json=model.model_dump(mode="json"))
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def _create_candidate(client: AsyncClient, resource_ids: list[int]) -> int:
    resp = await client.post(
        "/oil-gas-fields/merge-candidates",
        json={"resource_ids": resource_ids},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


class TestMergeCandidateDetailIntegration:
    @pytest.mark.anyio
    async def test_detail_includes_compare_tagged_with_resource_ids(
        self,
        integration_client: AsyncClient,
        og_create_res_fact: ResourceCreateFactory,
    ):
        id_a = await _create_resource(integration_client, og_create_res_fact, "Ghawar")
        id_b = await _create_resource(integration_client, og_create_res_fact, "Burgan")
        candidate_id = await _create_candidate(integration_client, [id_a, id_b])

        resp = await integration_client.get(
            f"/oil-gas-fields/merge-candidates/{candidate_id}"
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()

        assert body["status"] == "PENDING"
        assert body["resource_ids"] == [id_a, id_b]
        # `resources` detail objects were dropped; `compare` carries everything.
        assert "resources" not in body

        # `compare`: one entry per field; each value tagged with its source and
        # the resource it is attached to (source_id, value, priority, resource_id).
        compare = {c["field"]: c for c in body["compare"]}
        name_cmp = compare["name"]
        for entry in name_cmp["values"]:
            assert {
                "source",
                "source_id",
                "value",
                "priority",
                "resource_id",
            } <= set(entry)

        # The two resources resolve `name` to different values -> different.
        assert name_cmp["status"] == "different"
        assert name_cmp["values"][0]["value"] == "Ghawar"  # winner-first by priority
        # each source is attributed to the resource it is attached to
        rmi_by_resource = {
            (v["resource_id"], v["value"])
            for v in name_cmp["values"]
            if v["source"] == "rmi"
        }
        assert {(id_a, "Ghawar"), (id_b, "Burgan")} <= rmi_by_resource

    @pytest.mark.anyio
    async def test_detail_after_approve_is_live_null_shell(
        self,
        integration_client: AsyncClient,
        og_create_res_fact: ResourceCreateFactory,
    ):
        id_a = await _create_resource(integration_client, og_create_res_fact, "Ghawar")
        id_b = await _create_resource(integration_client, og_create_res_fact, "Burgan")
        candidate_id = await _create_candidate(integration_client, [id_a, id_b])

        approve = await integration_client.post(
            f"/oil-gas-fields/merge-candidates/{candidate_id}/approve",
            json={"review_notes": "ok"},
        )
        assert approve.status_code == 200, approve.text
        assert approve.json()["merged_resource_id"] is not None

        resp = await integration_client.get(
            f"/oil-gas-fields/merge-candidates/{candidate_id}"
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()

        assert body["status"] == "APPROVED"
        assert body["merged_resource_id"] is not None
        assert body["resource_ids"] == [id_a, id_b]
        assert "resources" not in body
        # Live compute: originals are repointed with memberships INACTIVE, so no
        # sources survive -> both resources are null everywhere, so every field
        # matches with no values. (Freeze snapshot is deferred.)
        for entry in body["compare"]:
            assert entry["status"] == "match"
            assert entry["values"] == []

    @pytest.mark.anyio
    async def test_per_resource_override_is_reverted_by_merge(
        self,
        integration_client: AsyncClient,
        integration_session_factory: async_sessionmaker[AsyncSession],
        og_field_resource_factory,
        source_maker,
    ):
        # Resource A carries RMI "RMI-name" (default winner) and GEM "GEM-name".
        id_a = await _create_resource_with_sources(
            integration_client,
            og_field_resource_factory,
            [
                source_maker(source="rmi", managed=False, name="RMI-name"),
                source_maker(source="gem", managed=False, name="GEM-name"),
            ],
        )
        id_b = await _create_resource_with_sources(
            integration_client,
            og_field_resource_factory,
            [source_maker(source="rmi", managed=False, name="B-name")],
        )

        # Override A's ordering so GEM outranks RMI for the NAME field -> A's
        # coalesced name flips. Overrides are per-field, per-source-record now, so
        # curate GEM's record for `name`.
        async with integration_session_factory() as session:
            gem_pk = await session.scalar(
                select(MembershipModel.source_pk).where(
                    MembershipModel.resource_id == id_a,
                    MembershipModel.source == "gem",
                )
            )
            session.add(
                OGFieldResourceSourcePriority(
                    resource_id=id_a,
                    source="gem",
                    source_pk=gem_pk,
                    colname="name",
                    priority=0,
                    created_by_id=1,
                    last_updated_by_id=1,
                )
            )
            await session.commit()

        # A's coalesced value reflects the override: its name resolves to GEM's.
        detail_a = await integration_client.get(f"/oil-gas-fields/{id_a}/detail")
        assert detail_a.status_code == 200, detail_a.text
        assert detail_a.json()["data"]["name"] == "GEM-name"  # override in effect

        candidate_id = await _create_candidate(integration_client, [id_a, id_b])
        resp = await integration_client.get(
            f"/oil-gas-fields/merge-candidates/{candidate_id}"
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()

        # A resolves `name` to its override value (GEM-name), B to B-name, so the
        # resources differ. `values` is winner-first by default priority (RMI),
        # and both of A's sources are attributed to resource A.
        name_cmp = next(c for c in body["compare"] if c["field"] == "name")
        assert name_cmp["status"] == "different"
        assert name_cmp["values"][0]["value"] == "RMI-name"
        a_values = {
            (v["source"], v["value"])
            for v in name_cmp["values"]
            if v["resource_id"] == id_a
        }
        assert {("rmi", "RMI-name"), ("gem", "GEM-name")} <= a_values

        # Approving materializes the reset: the merged resource has no override
        # rows and resolves `name` in default order (RMI), dropping the override.
        approve = await integration_client.post(
            f"/oil-gas-fields/merge-candidates/{candidate_id}/approve",
        )
        assert approve.status_code == 200, approve.text
        merged_id = approve.json()["merged_resource_id"]
        assert merged_id is not None

        merged = await integration_client.get(f"/oil-gas-fields/{merged_id}/detail")
        assert merged.status_code == 200, merged.text
        assert merged.json()["data"]["name"] == "RMI-name"

        async with integration_session_factory() as session:
            overrides = (
                await session.execute(
                    select(OGFieldResourceSourcePriority).where(
                        OGFieldResourceSourcePriority.resource_id == merged_id
                    )
                )
            ).all()
        assert overrides == []

    @pytest.mark.anyio
    async def test_composite_resource_matches_when_winners_agree(
        self,
        integration_client: AsyncClient,
        og_field_resource_factory,
        source_maker,
    ):
        # Resource A is "composite": two basin sources, RMI (winner) = "Foo" and
        # GEM = "Bar", so A resolves basin to "Foo".
        id_a = await _create_resource_with_sources(
            integration_client,
            og_field_resource_factory,
            [
                source_maker(source="rmi", managed=False, basin="Foo"),
                source_maker(source="gem", managed=False, basin="Bar"),
            ],
        )
        # Resource B has a single basin source = "Foo".
        id_b = await _create_resource_with_sources(
            integration_client,
            og_field_resource_factory,
            [source_maker(source="rmi", managed=False, basin="Foo")],
        )

        candidate_id = await _create_candidate(integration_client, [id_a, id_b])
        resp = await integration_client.get(
            f"/oil-gas-fields/merge-candidates/{candidate_id}"
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()

        basin = next(c for c in body["compare"] if c["field"] == "basin")
        # Both resources resolve basin to "Foo" (A's RMI winner beats its GEM
        # "Bar"), so despite three sources in play the field matches.
        assert basin["status"] == "match"
        assert {
            (v["resource_id"], v["source"], v["value"]) for v in basin["values"]
        } == {
            (id_a, "rmi", "Foo"),
            (id_a, "gem", "Bar"),
            (id_b, "rmi", "Foo"),
        }


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("prior_candidates", "apply_merges", "expected_created", "expected_skipped"),
    [
        ((), False, 0, 0),
        ((), True, 2, 0),
        ((0,), True, 1, 1),
        ((0,), False, 0, 1),
        ((0, 1), True, 0, 2),
        ((2,), True, 2, 0),
    ],
    ids=[
        "dry-run-writes-nothing",
        "real-run-creates-one-per-group",
        "real-run-skips-the-group-that-already-has-a-candidate",
        "dry-run-skips-match-the-real-run",
        "repeat-real-run-creates-nothing",
        "a-candidate-outside-the-matched-groups-is-ignored",
    ],
)
async def test_link_all_counts_and_writes(
    integration_client: AsyncClient,
    og_create_res_fact: ResourceCreateFactory,
    prior_candidates: tuple[int, ...],
    apply_merges: bool,
    expected_created: int,
    expected_skipped: int,
):
    ids = [
        await _create_resource(integration_client, og_create_res_fact, f"Field {n}")
        for n in range(6)
    ]
    pairs = [(ids[0], ids[1]), (ids[2], ids[3]), (ids[4], ids[5])]
    groups = pairs[:2]
    for index in prior_candidates:
        await _create_candidate(integration_client, list(pairs[index]))

    with patch.object(link_actions, "match", autospec=True) as match:
        match.return_value = groups
        resp = await integration_client.post(
            "/oil-gas-fields/merge-candidates/link-all",
            params={"apply_merges": apply_merges},
        )

    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "apply_merges": apply_merges,
        "match_groups": [list(group) for group in groups],
        "merge_candidates_created": expected_created,
        "merge_candidates_skipped": expected_skipped,
    }

    expected_persisted = {frozenset(pairs[i]) for i in prior_candidates}
    if apply_merges:
        expected_persisted |= {frozenset(group) for group in groups}

    listed = await integration_client.get("/oil-gas-fields/merge-candidates")
    assert listed.status_code == 200, listed.text
    assert {
        frozenset(candidate["resource_ids"]) for candidate in listed.json()
    } == expected_persisted


@pytest.mark.anyio
async def test_link_all_reports_a_failed_commit_instead_of_success(
    integration_client: AsyncClient,
    og_create_res_fact: ResourceCreateFactory,
):
    """A commit that fails must not surface as a 200 describing writes that rolled back."""
    id_a = await _create_resource(integration_client, og_create_res_fact, "Ghawar")
    id_b = await _create_resource(integration_client, og_create_res_fact, "Ghawar")

    async def failing_commit(self):
        raise OperationalError("COMMIT", {}, Exception("connection lost"))

    with (
        patch.object(link_actions, "match", autospec=True) as match,
        patch.object(UnitOfWork, "commit", failing_commit),
    ):
        match.return_value = [(id_a, id_b)]
        resp = await integration_client.post(
            "/oil-gas-fields/merge-candidates/link-all?apply_merges=true"
        )

    assert resp.status_code == 503, resp.text
    assert resp.json() == {"detail": "Database unavailable."}

    listed = await integration_client.get("/oil-gas-fields/merge-candidates")
    assert listed.status_code == 200, listed.text
    assert listed.json() == []


@pytest.mark.anyio
async def test_link_all_matches_only_the_callers_licensed_sources(
    integration_client: AsyncClient,
):
    app.dependency_overrides[get_token_claims] = lambda: TokenClaims(
        sub="test|user-1",
        permissions=frozenset({SOURCE_READ_GEM, MERGE_CANDIDATE_CREATE}),
    )

    with patch.object(link_actions, "match", autospec=True) as match:
        match.return_value = []
        resp = await integration_client.post(
            "/oil-gas-fields/merge-candidates/link-all"
        )

    assert resp.status_code == 200, resp.text
    assert match.call_args.kwargs["licensed_sources"] == frozenset({"gem"})
