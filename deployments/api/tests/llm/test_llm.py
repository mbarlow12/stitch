import json
from typing import Any

import pytest
from stitch.ogsi.model import GemSourceView, OGFieldDetailView
from stitch.ogsi.model.og_field import OilGasFieldBase

from stitch.api import llm

RESOURCE_ID = 42


def _detail_view() -> OGFieldDetailView:
    return OGFieldDetailView(
        id=RESOURCE_ID,
        data=OilGasFieldBase(
            name="Alpha Field",
            country="USA",
            basin="Permian",
            field_status="Producing",
        ),
        provenance={"name": "gem", "country": "gem"},
        source_data=[
            GemSourceView(
                id=7,
                name="Alpha Field",
                country="USA",
                basin="Permian",
            )
        ],
    )


def _response_payload(
    *, value: str, rationale: str, annotations: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "model": "gpt-test",
        "output": [
            {
                "content": [
                    {
                        "type": "output_text",
                        "text": f"VALUE: {value}\nRATIONALE: {rationale}",
                        "annotations": annotations,
                    }
                ]
            }
        ],
    }


class _RecordingClient:
    def __init__(self, recorder: dict[str, Any], payload: dict[str, Any]) -> None:
        self._recorder = recorder
        self._payload = payload

    async def __aenter__(self) -> "_RecordingClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def generate_field_suggestion(
        self, *, input_messages: list[dict[str, str]]
    ) -> llm.AzureResponsesResult:
        self._recorder["input_messages"] = input_messages
        return llm.AzureResponsesResult(
            output_text=self._payload["output"][0]["content"][0]["text"],
            model=self._payload["model"],
            response_payload=self._payload,
        )


@pytest.fixture
def recorder() -> dict[str, Any]:
    return {}


@pytest.fixture
def patched_llm(monkeypatch, recorder):
    detail_view = _detail_view()

    async def fake_load_suggestion_context(
        *, session, resource_id, licensed_sources=None
    ) -> OGFieldDetailView:
        recorder["load_args"] = {
            "session": session,
            "resource_id": resource_id,
            "licensed_sources": licensed_sources,
        }
        return detail_view

    monkeypatch.setattr(llm, "load_suggestion_context", fake_load_suggestion_context)

    def install(payload: dict[str, Any]) -> None:
        monkeypatch.setattr(
            llm,
            "AzureResponsesClient",
            lambda *args, **kwargs: _RecordingClient(recorder, payload),
        )

    return install


@pytest.mark.anyio
async def test_builds_prompt_from_detail_view(mock_session, patched_llm, recorder):
    patched_llm(
        _response_payload(
            value="Permian",
            rationale="The sources agree.",
            annotations=[
                {"type": "url_citation", "url": "https://example.com/a", "title": "A"}
            ],
        )
    )

    await llm.suggest_field_value(
        session=mock_session, resource_id=RESOURCE_ID, field="basin"
    )

    system_message, user_message = recorder["input_messages"]
    assert system_message["role"] == "system"
    assert "VALUE: <value or null>" in system_message["content"]
    assert "RATIONALE: <one short sentence>" in system_message["content"]

    assert user_message["role"] == "user"
    payload = json.loads(user_message["content"])
    assert payload["field"] == "basin"
    assert payload["resource_id"] == RESOURCE_ID
    assert payload["coalesced_resource"]["name"] == "Alpha Field"
    assert payload["coalesced_resource"]["basin"] == "Permian"
    assert [record["source"] for record in payload["source_records"]] == ["gem"]
    assert payload["source_records"][0]["name"] == "Alpha Field"


@pytest.mark.anyio
async def test_returns_value_citations_and_model(mock_session, patched_llm):
    patched_llm(
        _response_payload(
            value="Midland",
            rationale="Public sources name the Midland basin.",
            annotations=[
                {
                    "type": "url_citation",
                    "url": "https://example.com/basin",
                    "title": "Basin report",
                }
            ],
        )
    )

    suggestion = await llm.suggest_field_value(
        session=mock_session, resource_id=RESOURCE_ID, field="basin"
    )

    assert suggestion.value == "Midland"
    assert suggestion.citations == [
        llm.Citation(url="https://example.com/basin", title="Basin report")
    ]
    assert suggestion.rationale == "Public sources name the Midland basin."
    assert suggestion.model == "gpt-test"


@pytest.mark.anyio
async def test_uncited_value_is_dropped(mock_session, patched_llm):
    patched_llm(
        _response_payload(
            value="Midland",
            rationale="No public evidence was found.",
            annotations=[],
        )
    )

    suggestion = await llm.suggest_field_value(
        session=mock_session, resource_id=RESOURCE_ID, field="basin"
    )

    assert suggestion.value is None
    assert suggestion.citations == []


@pytest.mark.anyio
async def test_out_of_vocabulary_enum_value_is_rejected(mock_session, patched_llm):
    patched_llm(
        _response_payload(
            value="definitely-not-a-status",
            rationale="The model invented a status.",
            annotations=[{"type": "url_citation", "url": "https://example.com/status"}],
        )
    )

    with pytest.raises(llm.ModelOutputError):
        await llm.suggest_field_value(
            session=mock_session, resource_id=RESOURCE_ID, field="field_status"
        )
