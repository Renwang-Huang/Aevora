"""Machine-readable grammar for untrusted observation-use reports."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def _omit_optional_default(schema: dict) -> None:
    # Omission is allowed, explicit null is not. A null default on an integer
    # makes the generated JSON Schema invalid in the native Go MCP SDK.
    schema["properties"]["elapsed_seconds"].pop("default", None)


class ObservationUseReport(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra=_omit_optional_default)
    candidate_id: str = Field(min_length=1, max_length=240, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/@+\-]{0,239}$")
    report_key: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
    purpose: Literal["DEBUGGING", "PLANNING", "IMPLEMENTATION", "VALIDATION", "OTHER"]
    disposition: Literal["INVESTIGATED", "REUSED", "REJECTED", "NOT_RELEVANT", "INCONCLUSIVE"]
    reason: str = Field(min_length=1, max_length=800, description="Public reason without private paths or credentials")
    elapsed_seconds: int = Field(default=None, ge=0, le=86400, strict=True, description="Optional reported time; omit when unknown")
