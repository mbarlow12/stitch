from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings


class OTelSettings(BaseSettings):
    otel_enabled: bool = True
    otel_traces_exporter: Literal["console", "otlp", "none"] = "console"
    otel_exporter_otlp_endpoint: str | None = None
    otel_sample_ratio: float = Field(default=1.0, ge=0.0, le=1.0)
