"""Auditable engineering inputs for a wind hazard comparison.

These are submitted, reviewer-attested facts. The system checks their internal
consistency; it does not independently certify the engineering documents.
"""

from __future__ import annotations

from calendar import isleap
from datetime import datetime
from typing import Literal, Self
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator

from .common import ContractModel


def _https_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("evidence source must be an HTTPS URL")
    return value


class AnnualWindPressure(ContractModel):
    """One annual maximum in the approved, comparable pressure basis."""

    year: int = Field(ge=1940, le=2100)
    maximum_pa: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    valid_days: int = Field(ge=0, le=366)
    expected_days: int = Field(ge=365, le=366)
    source_url: str
    dataset: str = Field(min_length=1)
    grid_reference: str = Field(min_length=1)

    @field_validator("source_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return _https_url(value)

    @model_validator(mode="after")
    def validate_year(self) -> Self:
        if self.expected_days != (366 if isleap(self.year) else 365):
            raise ValueError("expected_days must match the calendar year")
        if self.valid_days > self.expected_days:
            raise ValueError("valid_days cannot exceed expected_days")
        if self.valid_days == 0 and self.maximum_pa is not None:
            raise ValueError("a year without valid days cannot have a maximum")
        return self


class WindEngineeringEvidence(ContractModel):
    """Human-attested manufacturer, mounting and project-side evidence."""

    component_model: str = Field(min_length=1)
    manufacturer: str = Field(min_length=1)
    manual_url: str
    manual_version: str = Field(min_length=1)
    manual_page: str = Field(min_length=1)
    capacity_pa: float = Field(gt=0, allow_inf_nan=False)
    capacity_definition: str = Field(min_length=1)
    required_mounting: str = Field(min_length=1)
    observed_mounting: str = Field(min_length=1)
    mounting_match: bool | None = None
    mounting_material_ids: list[str] = Field(default_factory=list)
    installation_reviewer: str | None = None
    installation_reviewed_at: datetime | None = None
    project_location_confirmed: bool = False
    location_evidence: str | None = None
    comparison_basis: str | None = None
    comparison_method_reference: str | None = None
    comparison_reviewer: str | None = None
    comparison_reviewed_at: datetime | None = None
    annual_pressures: list[AnnualWindPressure] = Field(default_factory=list)

    @field_validator("manual_url")
    @classmethod
    def validate_manual_url(cls, value: str) -> str:
        return _https_url(value)

    @model_validator(mode="after")
    def validate_records(self) -> Self:
        years = [item.year for item in self.annual_pressures]
        if len(years) != len(set(years)):
            raise ValueError("duplicate annual wind years")
        if len(self.mounting_material_ids) != len(set(self.mounting_material_ids)):
            raise ValueError("duplicate mounting material IDs")
        return self


class WindAnnualResult(ContractModel):
    year: int
    maximum_pa: float | None = None
    valid_days: int
    expected_days: int
    included: bool
    reason: str
    source_url: str
    dataset: str
    grid_reference: str


class WindComparisonResult(ContractModel):
    """R and F are historical sample comparisons, not loss probabilities."""

    status: Literal["calculated", "incomplete", "incompatible"]
    capacity_pa: float | None = None
    historical_maximum_pa: float | None = None
    r_historical_over_capacity: float | None = None
    f_exceedance_percent: float | None = None
    valid_year_count: int = 0
    excluded_year_count: int = 0
    annual_results: list[WindAnnualResult] = Field(default_factory=list)
    technical_result: Literal[
        "historical_exceedance", "within_historical_sample", "undetermined"
    ] = "undetermined"
    missing_requirements: list[str] = Field(default_factory=list)
    method_reference: str | None = None
    explanation: str = Field(min_length=1)
