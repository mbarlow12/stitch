import json
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pytest_mock import MockerFixture
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


def _canned_result(
    *, value: str, rationale: str, annotations: list[dict[str, Any]]
) -> llm.AzureResponsesResult:
    output_text = f"VALUE: {value}\nRATIONALE: {rationale}"
    return llm.AzureResponsesResult(
        output_text=output_text,
        model="gpt-test",
        response_payload={
            "model": "gpt-test",
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": output_text,
                            "annotations": annotations,
                        }
                    ]
                }
            ],
        },
    )


@pytest.fixture
def load_context(mocker: MockerFixture) -> AsyncMock:
    return mocker.patch.object(
        llm, "load_suggestion_context", return_value=_detail_view()
    )


@pytest.fixture
def azure_client(mocker: MockerFixture) -> AsyncMock:
    factory = mocker.patch.object(llm, "AzureResponsesClient")
    return factory.return_value.__aenter__.return_value


@pytest.mark.anyio
async def test_builds_prompt_from_detail_view(
    mocker: MockerFixture, mock_session, load_context, azure_client
):
    build_prompt = mocker.spy(llm, "build_field_suggestion_input")
    azure_client.generate_field_suggestion.return_value = _canned_result(
        value="Permian",
        rationale="The sources agree.",
        annotations=[
            {"type": "url_citation", "url": "https://example.com/a", "title": "A"}
        ],
    )

    await llm.suggest_field_value(
        session=mock_session, resource_id=RESOURCE_ID, field="basin"
    )

    sent = azure_client.generate_field_suggestion.await_args.kwargs["input_messages"]
    assert sent == build_prompt.spy_return

    system_message, user_message = build_prompt.spy_return
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
async def test_returns_value_citations_and_model(
    mock_session, load_context, azure_client
):
    azure_client.generate_field_suggestion.return_value = _canned_result(
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
async def test_uncited_value_is_dropped(mock_session, load_context, azure_client):
    azure_client.generate_field_suggestion.return_value = _canned_result(
        value="Midland",
        rationale="No public evidence was found.",
        annotations=[],
    )

    suggestion = await llm.suggest_field_value(
        session=mock_session, resource_id=RESOURCE_ID, field="basin"
    )

    assert suggestion.value is None
    assert suggestion.citations == []


@pytest.mark.anyio
async def test_out_of_vocabulary_enum_value_is_rejected(
    mock_session, load_context, azure_client
):
    azure_client.generate_field_suggestion.return_value = _canned_result(
        value="definitely-not-a-status",
        rationale="The model invented a status.",
        annotations=[{"type": "url_citation", "url": "https://example.com/status"}],
    )

    with pytest.raises(llm.ModelOutputError):
        await llm.suggest_field_value(
            session=mock_session, resource_id=RESOURCE_ID, field="field_status"
        )
