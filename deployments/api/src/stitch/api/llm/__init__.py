from __future__ import annotations

import asyncio
import json
from collections.abc import Collection
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any, ClassVar, Literal, get_args

from openai import AsyncOpenAI, OpenAIError
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
    "SuggestedValue",
    "get_llm_client",
    "load_suggestion_context",
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


@lru_cache
def get_llm_client() -> AsyncOpenAI:
    settings = get_llm_settings()
    if not settings.azure_openai_configured:
        raise LLMConfigurationError("Azure OpenAI settings are not configured.")
    assert settings.azure_openai_base_url is not None
    assert settings.azure_openai_api_key is not None
    return AsyncOpenAI(
        base_url=str(settings.azure_openai_base_url),
        api_key=settings.azure_openai_api_key.get_secret_value(),
        timeout=settings.azure_openai_timeout_seconds,
        max_retries=0,
    )


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
    foundry_response: dict[str, Any]


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


class SuggestedValue[T](BaseModel):
    value: T
    rationale: str
    citations: list[Citation]

    @classmethod
    def model_parametrized_name(cls, params: tuple[type[Any], ...]) -> str:
        return cls.__name__


async def _suggest(
    *,
    client: AsyncOpenAI,
    resource_id: int,
    field: AllowedSuggestionField,
    detail_view: OGFieldDetailView,
    observed_at: datetime,
) -> FieldSuggestion:
    info = OilGasFieldBase.model_fields[field]
    description = info.description or field
    coalesced = json.dumps(detail_view.data.model_dump(mode="json"))
    sources = json.dumps(
        [source.model_dump(mode="json") for source in detail_view.source_data]
    )
    try:
        response = await client.responses.parse(
            model=get_llm_settings().azure_openai_model,
            instructions=(
                f"You infer the `{field}` value for one oil and gas field. That field "
                f"means: {description} Search the public web for evidence and cite "
                f"every page you use. Return a null value unless a public citation "
                f"supports it. Infer no field other than `{field}`."
            ),
            input=(
                f"Coalesced Stitch record:\n{coalesced}\n\n"
                f"Source records behind it:\n{sources}"
            ),
            tools=[{"type": "web_search"}],
            text_format=SuggestedValue[info.annotation],
            store=False,
        )
    except OpenAIError as exc:
        raise AzureResponsesError("Azure Responses request failed.") from exc
    except ValidationError as exc:
        raise ModelOutputError("Model output did not match the field schema.") from exc

    parsed = response.output_parsed
    if parsed is None:
        raise ModelOutputError("Model returned no parsed output.")

    cited = bool(parsed.citations)
    return FieldSuggestion(
        resource_id=resource_id,
        field=field,
        value=parsed.value if cited else None,
        citations=parsed.citations if cited else [],
        model=response.model,
        rationale=parsed.rationale,
        observed_at=observed_at,
        foundry_response=response.model_dump(mode="json"),
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

    client = get_llm_client()
    observed_at = datetime.now(UTC)
    calls = [
        _suggest(
            client=client,
            resource_id=resource_id,
            field=field,
            detail_view=detail_view,
            observed_at=observed_at,
        )
        for field in targets
    ]
    return list(await asyncio.gather(*calls))
