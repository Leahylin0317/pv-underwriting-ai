from datetime import date, datetime

from pydantic import Field, IPvAnyAddress

from .common import Bbox, ContractModel
from .enums import (
    InstallationType,
    MaterialCategory,
    MaterialParseStatus,
    MaterialQualityStatus,
    OcrValueStatus,
    ProjectType,
)


class ProjectInfo(ContractModel):
    """光伏项目和被保险标的信息。"""

    project_name: str | None
    insured_name: str | None
    project_entity: str | None = None
    project_type: ProjectType
    installation_type: InstallationType
    site_address: str | None
    province: str | None = None
    city: str | None = None
    district: str | None = None
    longitude: float | None = Field(ge=-180.0, le=180.0)
    latitude: float | None = Field(ge=-90.0, le=90.0)
    proposed_start_date: date | None
    component_model: str | None
    submission_ip: IPvAnyAddress | None = None


class Material(ContractModel):
    """一次投保提交中的单份材料。"""

    material_id: str = Field(min_length=1)
    category: MaterialCategory
    file_name: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")
    captured_at: datetime | None = None
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    quality_status: MaterialQualityStatus
    quality_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    quality_issues: list[str]
    parse_status: MaterialParseStatus


class OcrField(ContractModel):
    """从一份材料中提取的一项文字字段。"""

    field_id: str = Field(min_length=1)
    material_id: str = Field(min_length=1)
    field_name: str = Field(min_length=1)
    raw_value: str | None
    normalized_value: str | None
    value_status: OcrValueStatus
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: Bbox | None = None
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    evidence_text: str | None = None