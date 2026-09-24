from datetime import datetime
from typing import Self

from pydantic import Field, model_validator

from .common import ContractModel
from .enums import (
    DecisionType,
    MaterialReviewAction,
    ProcessingStatus,
    ProcessingStep,
)


class MaterialReview(ContractModel):
    """规则引擎对单份材料的审核结果。"""

    material_id: str = Field(min_length=1)
    action: MaterialReviewAction
    triggered_rule_ids: list[str]
    finding_ids: list[str]
    ocr_field_ids: list[str]
    reasons: list[str]
    missing_requirements: list[str]
    requires_manual_review: bool


class UnderwritingDecision(ContractModel):
    """整单综合核保意见。"""

    decision: DecisionType
    decisive_rule_ids: list[str]
    reasons: list[str]
    conditions: list[str]
    warnings: list[str]
    missing_requirements: list[str]
    generated_at: datetime


class ProcessingTrace(ContractModel):
    """一个核保处理步骤的运行留痕。"""

    step: ProcessingStep
    provider: str = Field(min_length=1)
    model: str | None = None
    started_at: datetime
    finished_at: datetime
    latency_ms: int = Field(ge=0)
    status: ProcessingStatus
    error_code: str | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_time_order(self) -> Self:
        if self.finished_at < self.started_at:
            raise ValueError("finished_at must not be before started_at")
        return self