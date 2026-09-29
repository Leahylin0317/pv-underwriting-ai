from collections import Counter
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from app.contracts import (
    CaptureView,
    ContractModel,
    DecisionType,
    Material,
    MaterialCategory,
    ProjectInfo,
)


class MockAnalyzeRequest(ContractModel):
    """Mock 核保接口接收的请求数据。"""

    case_id: str = Field(min_length=1)
    project: ProjectInfo
    materials: list[Material] = Field(
        min_length=1
    )


class UploadedMaterialManifest(
    ContractModel
):
    """一份上传文件对应的材料信息。"""

    material_id: str = Field(min_length=1)
    category: MaterialCategory
    capture_view: CaptureView = CaptureView.UNKNOWN


class RealAnalyzeManifest(ContractModel):
    """真实整单核保接口接收的案件清单。"""

    case_id: str = Field(min_length=1)
    project: ProjectInfo
    materials: list[
        UploadedMaterialManifest
    ] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_material_ids(self) -> Self:
        material_ids = [
            material.material_id
            for material in self.materials
        ]

        duplicate_ids = sorted(
            material_id
            for material_id, count
            in Counter(material_ids).items()
            if count > 1
        )

        if duplicate_ids:
            raise ValueError(
                "duplicate material IDs in "
                f"manifest: {duplicate_ids}"
            )

        return self


class HumanReviewSubmission(ContractModel):
    """A human underwriting decision recorded against a saved case."""

    reviewer_name: str = Field(min_length=1, max_length=100)
    final_decision: DecisionType
    comment: str = Field(min_length=1, max_length=4000)

    @field_validator("reviewer_name", "comment")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @model_validator(mode="after")
    def require_final_outcome(self) -> Self:
        if self.final_decision is DecisionType.MANUAL_REVIEW:
            raise ValueError("final_decision must be a completed underwriting outcome")
        return self


class LoginRequest(ContractModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class UserCreateRequest(ContractModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=12, max_length=256)
    role: Literal["viewer", "underwriter", "admin"]


class UserPasswordResetRequest(ContractModel):
    password: str = Field(min_length=12, max_length=256)
