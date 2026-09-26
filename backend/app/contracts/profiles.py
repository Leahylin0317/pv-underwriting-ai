from datetime import date, datetime
from typing import Self

from pydantic import Field, model_validator

from .common import ContractModel
from .enums import ExpectedLossRisk, ResistanceLevel


class ComponentProfile(ContractModel):
    """光伏组件型号及抗灾参数。"""

    component_model: str = Field(min_length=1)
    manufacturer: str | None = None
    rated_power_w: float | None = Field(default=None, gt=0.0)
    hail_resistance_mm: float | None = Field(default=None, gt=0.0)
    wind_load_pa: float | None = Field(default=None, gt=0.0)
    snow_load_pa: float | None = Field(default=None, gt=0.0)
    source_url: str | None
    source_name: str = Field(min_length=1)
    retrieved_at: datetime
    match_confidence: float = Field(ge=0.0, le=1.0)


class WeatherProfile(ContractModel):
    """项目所在地的历史气象数据。"""

    longitude: float = Field(ge=-180.0, le=180.0)
    latitude: float = Field(ge=-90.0, le=90.0)
    historical_max_wind_m_s: float | None = Field(default=None, ge=0.0)
    historical_max_hail_mm: float | None = Field(default=None, ge=0.0)
    historical_max_snow_load_pa: float | None = Field(default=None, ge=0.0)
    observation_start: date | None = None
    observation_end: date | None = None
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
        return self


class CatastropheAssessment(ContractModel):
    """组件能力与当地自然灾害数据的比较结果。"""

    resistance_level: ResistanceLevel
    expected_loss_risk: ExpectedLossRisk
    factors: list[str]
    explanation: str = Field(min_length=1)
    triggered_rule_ids: list[str]
    requires_manual_review: bool