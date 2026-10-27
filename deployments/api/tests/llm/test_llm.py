import json
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
    client = AsyncMock()
    mocker.patch.object(llm, "get_llm_client", return_value=client)
    return client


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


def _wire_client(handler, *, model: str = "gpt-test") -> llm.AzureResponsesClient:
    settings = llm.LLMSettings(
        azure_openai_base_url="https://fake.openai.azure.com/openai/v1/",
        azure_openai_api_key="test-key",
        azure_openai_model=model,
    )
    sdk = AsyncOpenAI(
        base_url=str(settings.azure_openai_base_url),
        api_key="test-key",
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
        max_retries=0,
    )
    return llm.AzureResponsesClient(settings=settings, client=sdk)


def _response_body(**overrides: Any) -> dict[str, Any]:
    body = {
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
                        "text": "VALUE: Midland\nRATIONALE: Sources agree.",
                        "annotations": [],
                    }
                ],
            }
        ],
        "parallel_tool_calls": False,
        "tool_choice": "auto",
        "tools": [],
    }
    body.update(overrides)
    return body


@pytest.mark.anyio
async def test_sends_responses_request_with_web_search_tool():
    captured: dict[str, Any] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content)
        return httpx2.Response(200, request=request, json=_response_body())

    client = _wire_client(handler)
    await client.generate_field_suggestion(
        input_messages=[{"role": "user", "content": "hi"}]
    )

    assert captured["method"] == "POST"
    assert captured["url"] == "https://fake.openai.azure.com/openai/v1/responses"
    assert captured["authorization"] == "Bearer test-key"
    assert captured["body"] == {
        "model": "gpt-test",
        "input": [{"role": "user", "content": "hi"}],
        "store": False,
        "tools": [{"type": "web_search"}],
    }


@pytest.mark.anyio
async def test_citations_survive_the_sdk_round_trip():
    annotated = _response_body()
    annotated["output"][0]["content"][0]["annotations"] = [
        {
            "type": "url_citation",
            "url": "https://example.com/a",
            "title": "A",
            "start_index": 0,
            "end_index": 1,
        }
    ]

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, request=request, json=annotated)

    result = await _wire_client(handler).generate_field_suggestion(
        input_messages=[{"role": "user", "content": "hi"}]
    )

    assert llm.extract_public_citations(result.response_payload) == [
        llm.Citation(url="https://example.com/a", title="A")
    ]


@pytest.mark.anyio
async def test_error_status_becomes_azure_responses_error():
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            500, request=request, json={"error": {"message": "boom"}}
        )

    with pytest.raises(llm.AzureResponsesError):
        await _wire_client(handler).generate_field_suggestion(
            input_messages=[{"role": "user", "content": "hi"}]
        )


@pytest.mark.anyio
async def test_error_payload_on_a_200_becomes_azure_responses_error():
    def handler(request: httpx2.Request) -> httpx2.Response:
        body = _response_body(error={"code": "server_error", "message": "boom"})
        return httpx2.Response(200, request=request, json=body)

    with pytest.raises(llm.AzureResponsesError):
        await _wire_client(handler).generate_field_suggestion(
            input_messages=[{"role": "user", "content": "hi"}]
        )


def test_unconfigured_settings_raise_configuration_error():
    with pytest.raises(llm.LLMConfigurationError):
        llm.AzureResponsesClient(settings=llm.LLMSettings(azure_openai_model=""))
