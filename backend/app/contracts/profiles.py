from datetime import date, datetime
from typing import Literal, Self

from pydantic import Field, model_validator

from .common import ContractModel
from .enums import ExpectedLossRisk, ParameterApplicabilityStatus, ResistanceLevel


class ComponentProfile(ContractModel):
    """光伏组件型号、厂家参数和参数证据。"""

    component_model: str = Field(min_length=1)
    model_aliases: list[str] = Field(default_factory=list)
    manufacturer: str | None = None
    rated_power_w: float | None = Field(default=None, gt=0.0)
    hail_resistance_mm: float | None = Field(default=None, gt=0.0)
    wind_load_pa: float | None = Field(default=None, gt=0.0)
    snow_load_pa: float | None = Field(default=None, gt=0.0)
    front_static_load_pa: float | None = Field(default=None, gt=0.0)
    back_static_load_pa: float | None = Field(default=None, gt=0.0)
    hail_impact_velocity_m_s: float | None = Field(default=None, gt=0.0)
    market_version: str | None = None
    model_derivation_method: str | None = None
    source_document_type: str | None = None
    source_note: str | None = None
    source_url: str | None
    source_name: str = Field(min_length=1)
    retrieved_at: datetime
    match_confidence: float = Field(ge=0.0, le=1.0)
    parameter_sources: dict[str, str] = Field(default_factory=dict)
    lookup_notes: list[str] = Field(default_factory=list)


class WeatherProfile(ContractModel):
    """项目点及所选气象网格的历史再分析数据和覆盖情况。"""

    longitude: float = Field(ge=-180.0, le=180.0)
    latitude: float = Field(ge=-90.0, le=90.0)
    historical_max_wind_m_s: float | None = Field(default=None, ge=0.0)
    historical_max_daily_wind_speed_m_s: float | None = Field(default=None, ge=0.0)
    historical_max_daily_precipitation_mm: float | None = Field(default=None, ge=0.0)
    historical_max_daily_rain_mm: float | None = Field(default=None, ge=0.0)
    historical_max_daily_precipitation_hours: float | None = Field(
        default=None, ge=0.0, le=24.0
    )
    historical_max_hail_mm: float | None = Field(default=None, ge=0.0)
    historical_max_snow_load_pa: float | None = Field(default=None, ge=0.0)
    historical_max_daily_snowfall_cm: float | None = Field(default=None, ge=0.0)
    observation_start: date | None = None
    observation_end: date | None = None
    returned_data_start: date | None = None
    returned_data_end: date | None = None
    expected_day_count: int | None = Field(default=None, ge=1)
    returned_day_count: int | None = Field(default=None, ge=0)
    wind_valid_day_count: int | None = Field(default=None, ge=0)
    wind_speed_valid_day_count: int | None = Field(default=None, ge=0)
    precipitation_valid_day_count: int | None = Field(default=None, ge=0)
    rain_valid_day_count: int | None = Field(default=None, ge=0)
    precipitation_hours_valid_day_count: int | None = Field(default=None, ge=0)
    snowfall_valid_day_count: int | None = Field(default=None, ge=0)
    grid_longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    grid_latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    grid_distance_km: float | None = Field(default=None, ge=0.0)
    grid_elevation_m: float | None = None
    timezone: str | None = None
    dataset_selection: str | None = None
    grid_selection_method: str | None = None
    wind_unit: str | None = None
    wind_speed_unit: str | None = None
    precipitation_unit: str | None = None
    rain_unit: str | None = None
    precipitation_hours_unit: str | None = None
    snowfall_unit: str | None = None
    data_quality_notes: list[str] = Field(default_factory=list)
    source_name: str = Field(min_length=1)
    source_url: str | None = None
    retrieved_at: datetime

    @model_validator(mode="after")
    def validate_observation_period(self) -> Self:
        if (
            self.observation_start is not None
            and self.observation_end is not None
            and self.observation_start > self.observation_end
        ):
            raise ValueError("observation_start must not be after observation_end")
        if (self.grid_longitude is None) != (self.grid_latitude is None):
            raise ValueError("grid_longitude and grid_latitude must be provided together")
        for field_name in (
            "returned_day_count",
            "wind_valid_day_count",
            "wind_speed_valid_day_count",
            "precipitation_valid_day_count",
            "rain_valid_day_count",
            "precipitation_hours_valid_day_count",
            "snowfall_valid_day_count",
        ):
            value = getattr(self, field_name)
            if (
                value is not None
                and self.expected_day_count is not None
                and value > self.expected_day_count
            ):
                raise ValueError(f"{field_name} must not exceed expected_day_count")
        if (
            self.returned_data_start is not None
            and self.returned_data_end is not None
            and self.returned_data_start > self.returned_data_end
        ):
            raise ValueError("returned_data_start must not be after returned_data_end")
        return self


class InstallationParameterReview(ContractModel):
    """逐灾种记录参数能否用于实际安装配置的核验状态。"""

    hazard: Literal["wind", "hail", "snow"]
    parameter_fields: list[str]
    status: ParameterApplicabilityStatus
    explanation: str = Field(min_length=1)
    required_evidence: list[str]
    triggered_rule_id: str = Field(min_length=1)


class CatastropheAssessment(ContractModel):
    """组件能力与当地自然灾害数据的比较结果。"""

    resistance_level: ResistanceLevel
    expected_loss_risk: ExpectedLossRisk
    factors: list[str]
    explanation: str = Field(min_length=1)
    triggered_rule_ids: list[str]
    requires_manual_review: bool
    installation_parameter_reviews: list[InstallationParameterReview] = Field(
        default_factory=list
    )
    critical_shortfall_ratio: float | None = Field(default=None, gt=0.0, lt=1.0)
    adequate_margin_ratio: float | None = Field(default=None, gt=1.0)
