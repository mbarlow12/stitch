import asyncio
import json
import re
from typing import Any
from unittest.mock import AsyncMock

import httpx2
import pytest
from openai import AsyncOpenAI
from pytest_mock import MockerFixture
from stitch.ogsi.model import GemSourceView, OGFieldDetailView
from stitch.ogsi.model.og_field import OilGasFieldBase

from stitch.api import llm

RESOURCE_ID = 42
DETAIL_ID = 7


def _detail_view(**values: Any) -> OGFieldDetailView:
    return OGFieldDetailView(
        id=DETAIL_ID,
        data=OilGasFieldBase(**{"name": "Alpha Field", "country": None, **values}),
        provenance={"name": "gem"},
        source_data=[
            GemSourceView(id=7, name="Alpha Field", country="USA", basin="Permian")
        ],
    )


def _response_body(parsed: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": "resp_1",
        "object": "response",
        "created_at": 0,
        "model": "gpt-test",
        "status": "completed",
        "output": [
            {
                "id": "msg_1",
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps(parsed),
                        "annotations": [],
                    }
                ],
            }
        ],
        "parallel_tool_calls": False,
        "tool_choice": "auto",
        "tools": [],
    }
    return body | overrides


def _use_client(mocker: MockerFixture, handler) -> None:
    client = AsyncOpenAI(
        base_url="https://fake.openai.azure.com/openai/v1/",
        api_key="test-key",
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
        max_retries=0,
    )
    mocker.patch.object(llm, "get_llm_client", return_value=client)


def _responder(body: dict[str, Any], captured: dict[str, Any] | None = None):
    def handler(request: httpx2.Request) -> httpx2.Response:
        if captured is not None:
            captured.update(json.loads(request.content))
        return httpx2.Response(200, request=request, json=body)

    return handler


def _suggest(session, fields: list[str]) -> list[llm.FieldSuggestion]:
    return asyncio.run(
        llm.suggest_missing_field_values(
            session=session, resource_id=RESOURCE_ID, fields=fields
        )
    )


def _value_schema(body: dict[str, Any]) -> dict[str, Any]:
    schema = body["text"]["format"]["schema"]["properties"]["value"]
    branches = schema.get("anyOf", [schema])
    return {key: value for branch in branches for key, value in branch.items()}


@pytest.fixture
def load_context(mocker: MockerFixture) -> AsyncMock:
    return mocker.patch.object(
        llm, "load_suggestion_context", return_value=_detail_view()
    )


@pytest.mark.parametrize(
    ("field", "value", "expected_schema"),
    [
        (
            "field_status",
            "Producing",
            {"enum": ["Producing", "Non-Producing", "Abandoned", "Planned"]},
        ),
        ("discovery_year", 1998, {"minimum": 1700, "maximum": 2100}),
        ("country", "USA", {"pattern": "^[A-Z]{3}$"}),
    ],
)
def test_request_carries_web_search_and_the_field_schema(
    mocker, mock_session, load_context, field, value, expected_schema
):
    captured: dict[str, Any] = {}
    parsed = {"value": value, "rationale": "Sources agree.", "citations": []}
    _use_client(mocker, _responder(_response_body(parsed), captured))

    _suggest(mock_session, [field])

    assert captured["tools"] == [{"type": "web_search"}]
    assert captured["store"] is False
    assert re.fullmatch(r"[A-Za-z0-9_-]{1,64}", captured["text"]["format"]["name"])
    assert expected_schema.items() <= _value_schema(captured).items()


def test_result_carries_value_citations_model_and_response(
    mocker, mock_session, load_context
):
    parsed = {
        "value": "Midland",
        "rationale": "Public sources name the Midland basin.",
        "citations": [{"url": "https://example.com/basin", "title": "Basin report"}],
    }
    _use_client(mocker, _responder(_response_body(parsed)))

    suggestions = _suggest(mock_session, ["basin"])

    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert suggestion.field == "basin"
    assert suggestion.value == "Midland"
    assert suggestion.rationale == "Public sources name the Midland basin."
    assert suggestion.citations == [
        llm.Citation(url="https://example.com/basin", title="Basin report")
    ]
    assert suggestion.model == "gpt-test"
    assert suggestion.resource_id == RESOURCE_ID
    assert suggestion.foundry_response["id"] == "resp_1"


def test_only_missing_fields_are_requested(mocker, mock_session):
    mocker.patch.object(
        llm,
        "load_suggestion_context",
        return_value=_detail_view(basin="Permian", discovery_year=None),
    )
    parsed = {"value": 1998, "rationale": "Sources agree.", "citations": []}
    _use_client(mocker, _responder(_response_body(parsed)))

    suggestions = _suggest(mock_session, ["basin", "discovery_year"])

    assert [suggestion.field for suggestion in suggestions] == ["discovery_year"]


def test_uncited_value_is_dropped(mocker, mock_session, load_context):
    parsed = {"value": "Midland", "rationale": "No public evidence.", "citations": []}
    _use_client(mocker, _responder(_response_body(parsed)))

    suggestions = _suggest(mock_session, ["basin"])

    assert suggestions[0].value is None
    assert suggestions[0].citations == []


def _failing_status(request: httpx2.Request) -> httpx2.Response:
    return httpx2.Response(500, request=request, json={"error": {"message": "boom"}})


def _failing_connection(request: httpx2.Request) -> httpx2.Response:
    raise httpx2.ConnectError("no route to host", request=request)


@pytest.mark.parametrize("handler", [_failing_status, _failing_connection])
def test_request_failures_become_azure_responses_error(
    mocker, mock_session, load_context, handler
):
    _use_client(mocker, handler)

    with pytest.raises(llm.AzureResponsesError):
        _suggest(mock_session, ["basin"])


def test_missing_message_item_becomes_model_output_error(
    mocker, mock_session, load_context
):
    body = _response_body({"value": None, "rationale": "", "citations": []}, output=[])
    _use_client(mocker, _responder(body))

    with pytest.raises(llm.ModelOutputError):
        _suggest(mock_session, ["basin"])
