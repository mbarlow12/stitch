from __future__ import annotations

import asyncio
import json
from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any, ClassVar, Literal, get_args

from openai import AsyncOpenAI
from openai import APIError as OpenAIAPIError
from pydantic import (
    AnyHttpUrl,
    BaseModel,
    Field,
    SecretStr,
    ValidationError,
    field_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from stitch.ogsi.model import OGFieldDetailView, OGSISrcKey
from stitch.ogsi.model.og_field import OilGasFieldBase
from stitch.ogsi.model.types import (
    FieldStatus,
    LocationType,
    PrimaryHydrocarbonGroup,
    ProductionConventionality,
)

from stitch.api.db import og_field_resource_actions
from stitch.api.db.utils import resource_to_detail_view

__all__ = [
    "ALL_SUGGESTION_FIELDS",
    "AllowedSuggestionField",
    "AzureResponsesError",
    "Citation",
    "FieldSuggestion",
    "LLMConfigurationError",
    "LLMServiceError",
    "ModelOutputError",
    "get_llm_client",
    "load_suggestion_context",
    "suggest_field_value",
    "suggest_missing_field_values",
]


class LLMServiceError(Exception): ...


class LLMConfigurationError(LLMServiceError): ...


class ModelOutputError(LLMServiceError): ...


class AzureResponsesError(LLMServiceError): ...


class LLMSettings(BaseSettings):
    azure_openai_base_url: AnyHttpUrl | None = Field(
        default=None,
        alias="STITCH_LLM_AZURE_OPENAI_BASE_URL",
        description="Azure OpenAI v1 base URL, for example https://<resource>.openai.azure.com/openai/v1",
    )
    azure_openai_api_key: SecretStr | None = Field(
        default=None,
        alias="STITCH_LLM_AZURE_OPENAI_API_KEY",
    )
    azure_openai_model: str | None = Field(
        default=None,
        alias="STITCH_LLM_AZURE_OPENAI_MODEL",
    )
    azure_openai_timeout_seconds: float = Field(
        default=30.0,
        alias="STITCH_LLM_AZURE_OPENAI_TIMEOUT_SECONDS",
    )

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @field_validator(
        "azure_openai_base_url",
        "azure_openai_api_key",
        "azure_openai_model",
        mode="before",
    )
    @classmethod
    def empty_strings_to_none(cls, value: object) -> object:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @property
    def azure_openai_configured(self) -> bool:
        return all(
            (
                self.azure_openai_base_url is not None,
                self.azure_openai_api_key is not None,
                self.azure_openai_model,
            )
        )


@lru_cache
def get_llm_settings() -> LLMSettings:
    return LLMSettings()


class Citation(BaseModel):
    url: str
    title: str | None = None


class FieldSuggestion(BaseModel):
    resource_id: int
    field: str
    value: Any
    citations: list[Citation]
    model: str
    rationale: str
    observed_at: datetime


async def load_suggestion_context(
    *,
    session: AsyncSession,
    resource_id: int,
    licensed_sources: Collection[OGSISrcKey] | None = None,
) -> OGFieldDetailView:
    resource = await og_field_resource_actions.get_resolved(
        session=session, id=resource_id, licensed_sources=licensed_sources
    )
    return resource_to_detail_view(resource)


AllowedSuggestionField = Literal[
    "name",
    "name_local",
    "country",
    "basin",
    "region",
    "state_province",
    "reservoir_formation",
    "discovery_year",
    "fid_year",
    "production_start_year",
    "location_type",
    "field_status",
    "primary_hydrocarbon_group",
    "production_conventionality",
]

ALL_SUGGESTION_FIELDS: tuple[AllowedSuggestionField, ...] = get_args(
    AllowedSuggestionField
)

STRING_FIELDS = frozenset(
    {
        "name",
        "name_local",
        "country",
        "basin",
        "region",
        "state_province",
        "reservoir_formation",
    }
)
YEAR_FIELDS = frozenset({"discovery_year", "fid_year", "production_start_year"})
ENUM_VALUES_BY_FIELD: dict[str, tuple[str, ...]] = {
    "location_type": get_args(LocationType),
    "field_status": get_args(FieldStatus),
    "primary_hydrocarbon_group": get_args(PrimaryHydrocarbonGroup),
    "production_conventionality": get_args(ProductionConventionality),
}


class ParsedFieldSuggestion:
    def __init__(self, *, value: Any, rationale: str) -> None:
        self.value = value
        self.rationale = rationale


def build_field_suggestion_input(
    *,
    resource_id: int,
    field: AllowedSuggestionField,
    detail_view: OGFieldDetailView,
) -> list[dict[str, str]]:
    field_info = OilGasFieldBase.model_fields[field]
    field_description = field_info.description or field.replace("_", " ")

    payload = {
        "task": "Infer one oil and gas field value from the provided Stitch record context.",
        "resource_id": resource_id,
        "field": field,
        "field_description": field_description,
        "instructions": [
            "Use only the provided coalesced_resource and source_records.",
            "Use web search to find publicly available evidence for the requested value.",
            "If you cannot support the value with one or more public citations, return VALUE: null.",
            "Return VALUE: null when the value cannot be inferred from the provided data.",
            "Do not use outside knowledge.",
            "Do not return a value for any field except the requested field.",
        ],
        "coalesced_resource": detail_view.data.model_dump(mode="json"),
        "source_records": [
            source.model_dump(mode="json") for source in detail_view.source_data
        ],
    }

    return [
        {
            "role": "system",
            "content": (
                "You infer one oil and gas field value from Stitch data. "
                "Use public web search evidence when needed. "
                "Respond using exactly two lines in this format:\n"
                "VALUE: <value or null>\n"
                "RATIONALE: <one short sentence>\n"
                "Do not output JSON. Do not add any extra lines."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False, indent=2),
        },
    ]


def parse_field_suggestion_response(raw_output_text: str) -> ParsedFieldSuggestion:
    non_empty_lines = [
        line.strip() for line in raw_output_text.splitlines() if line.strip()
    ]
    if len(non_empty_lines) != 2:
        raise ModelOutputError(
            "Model did not return the expected two-line VALUE/RATIONALE format."
        )

    value_prefix = "VALUE:"
    rationale_prefix = "RATIONALE:"
    value_raw, rationale_raw = non_empty_lines

    if not value_raw.startswith(value_prefix) or not rationale_raw.startswith(
        rationale_prefix
    ):
        raise ModelOutputError(
            "Model did not return the expected VALUE/RATIONALE format."
        )

    value_line = value_raw.partition(":")[2].strip()
    rationale_line = rationale_raw.partition(":")[2].strip()

    value: Any
    if value_line.lower() == "null":
        value = None
    else:
        value = value_line

    if not rationale_line:
        raise ModelOutputError("Model did not return a rationale.")

    return ParsedFieldSuggestion(value=value, rationale=rationale_line)


def sanitize_and_validate_suggested_value(
    *,
    detail_data: OilGasFieldBase,
    field: AllowedSuggestionField,
    value: Any,
) -> Any:
    sanitized = _sanitize_value(field=field, value=value)
    candidate = detail_data.model_copy(update={field: sanitized})

    try:
        validated = OilGasFieldBase.model_validate(candidate.model_dump(mode="python"))
    except ValidationError as exc:
        raise ModelOutputError("Suggested value failed OGSI model validation.") from exc

    return getattr(validated, field)


def _sanitize_value(*, field: AllowedSuggestionField, value: Any) -> Any:
    if value is None:
        return None

    if field in STRING_FIELDS:
        if not isinstance(value, str):
            raise ModelOutputError(f"Suggested value for `{field}` must be a string.")
        cleaned = value.strip()
        return cleaned or None

    if field in YEAR_FIELDS:
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned.isdigit():
                return int(cleaned)
        raise ModelOutputError(f"Suggested value for `{field}` must be an integer.")

    enum_values = ENUM_VALUES_BY_FIELD.get(field)
    if enum_values is not None:
        if not isinstance(value, str):
            raise ModelOutputError(f"Suggested value for `{field}` must be a string.")
        cleaned = value.strip()
        if not cleaned:
            return None
        by_casefold = {enum_value.casefold(): enum_value for enum_value in enum_values}
        try:
            return by_casefold[cleaned.casefold()]
        except KeyError as exc:
            raise ModelOutputError(
                f"Suggested value for `{field}` is not an allowed value."
            ) from exc

    raise AssertionError(f"Unsupported suggestion field: {field}")


@dataclass(frozen=True, slots=True)
class AzureResponsesResult:
    output_text: str
    model: str
    response_payload: dict[str, Any]


class AzureResponsesClient:
    def __init__(
        self,
        settings: LLMSettings | None = None,
        client: AsyncOpenAI | None = None,
    ) -> None:
        self._settings = settings or get_llm_settings()
        if not self._settings.azure_openai_configured:
            raise LLMConfigurationError("Azure OpenAI settings are not configured.")

        assert self._settings.azure_openai_base_url is not None
        assert self._settings.azure_openai_api_key is not None
        assert self._settings.azure_openai_model is not None

        self._model = self._settings.azure_openai_model
        self._owns_client = client is None
        self._client = client or AsyncOpenAI(
            base_url=str(self._settings.azure_openai_base_url),
            api_key=self._settings.azure_openai_api_key.get_secret_value(),
            timeout=self._settings.azure_openai_timeout_seconds,
            max_retries=0,
        )

    async def __aenter__(self) -> "AzureResponsesClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.close()

    async def generate_field_suggestion(
        self,
        *,
        input_messages: list[dict[str, str]],
    ) -> AzureResponsesResult:
        try:
            response = await self._client.responses.create(
                model=self._model,
                input=input_messages,
                store=False,
                tools=[{"type": "web_search"}],
            )
        except OpenAIAPIError as exc:
            raise AzureResponsesError("Azure Responses request failed.") from exc

        if response.error is not None:
            raise AzureResponsesError("Azure Responses returned an error payload.")
        if response.status is not None and response.status != "completed":
            raise AzureResponsesError(
                f"Azure Responses returned status {response.status}."
            )
        if not response.output_text:
            raise AzureResponsesError("Azure Responses did not return output text.")

        return AzureResponsesResult(
            output_text=response.output_text,
            model=response.model or self._model,
            response_payload=response.model_dump(mode="json"),
        )


@lru_cache
def get_llm_client() -> AzureResponsesClient:
    return AzureResponsesClient()


def extract_public_citations(body: dict[str, Any]) -> list[Citation]:
    citations: list[Citation] = []
    seen: set[tuple[str, str | None]] = set()

    output = body.get("output")
    if not isinstance(output, list):
        return citations

    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for content_item in content:
            if not isinstance(content_item, dict):
                continue
            annotations = content_item.get("annotations")
            if not isinstance(annotations, list):
                continue
            for annotation in annotations:
                if not isinstance(annotation, dict):
                    continue
                if annotation.get("type") != "url_citation":
                    continue
                url = annotation.get("url")
                title = annotation.get("title")
                if not isinstance(url, str):
                    continue
                if not url.startswith(("http://", "https://")):
                    continue
                if title is not None and not isinstance(title, str):
                    title = None
                key = (url, title)
                if key in seen:
                    continue
                seen.add(key)
                citations.append(Citation(url=url, title=title))

    return citations


async def _suggest_from_context(
    *,
    llm_client: AzureResponsesClient,
    resource_id: int,
    field: AllowedSuggestionField,
    detail_view: OGFieldDetailView,
) -> FieldSuggestion:
    observed_at = datetime.now(UTC)
    input_messages = build_field_suggestion_input(
        resource_id=resource_id,
        field=field,
        detail_view=detail_view,
    )

    llm_result = await llm_client.generate_field_suggestion(
        input_messages=input_messages
    )

    parsed = parse_field_suggestion_response(llm_result.output_text)
    citations = extract_public_citations(llm_result.response_payload)
    if parsed.value is None or not citations:
        value = None
        citations = []
    else:
        value = sanitize_and_validate_suggested_value(
            detail_data=detail_view.data,
            field=field,
            value=parsed.value,
        )

    return FieldSuggestion(
        resource_id=resource_id,
        field=field,
        value=value,
        citations=citations,
        model=llm_result.model,
        rationale=parsed.rationale,
        observed_at=observed_at,
    )


async def suggest_field_value(
    *,
    session: AsyncSession,
    resource_id: int,
    field: AllowedSuggestionField,
    licensed_sources: Collection[OGSISrcKey] | None = None,
) -> FieldSuggestion:
    detail_view = await load_suggestion_context(
        session=session,
        resource_id=resource_id,
        licensed_sources=licensed_sources,
    )

    return await _suggest_from_context(
        llm_client=get_llm_client(),
        resource_id=resource_id,
        field=field,
        detail_view=detail_view,
    )


async def suggest_missing_field_values(
    *,
    session: AsyncSession,
    resource_id: int,
    fields: Collection[AllowedSuggestionField] = ALL_SUGGESTION_FIELDS,
    licensed_sources: Collection[OGSISrcKey] | None = None,
) -> list[FieldSuggestion]:
    detail_view = await load_suggestion_context(
        session=session,
        resource_id=resource_id,
        licensed_sources=licensed_sources,
    )

    requested = set(fields)
    targets = [
        field
        for field in ALL_SUGGESTION_FIELDS
        if field in requested and getattr(detail_view.data, field) is None
    ]
    if not targets:
        return []

    llm_client = get_llm_client()
    return list(
        await asyncio.gather(
            *(
                _suggest_from_context(
                    llm_client=llm_client,
                    resource_id=resource_id,
                    field=field,
                    detail_view=detail_view,
                )
                for field in targets
            )
        )
    )
