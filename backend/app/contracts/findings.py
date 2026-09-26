from pydantic import Field

from .common import Bbox, ContractModel
from .enums import DetectionStatus, RiskCategory, RiskSeverity


class RiskFinding(ContractModel):
    """一项图片风险识别结果。"""

    finding_id: str = Field(min_length=1)
    material_id: str = Field(min_length=1)
    category: RiskCategory
    label: str = Field(min_length=1)
    detection_status: DetectionStatus
    severity: RiskSeverity
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: Bbox | None = None
    evidence_text: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    requires_manual_review: bool