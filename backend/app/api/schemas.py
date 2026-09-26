from collections import Counter
from typing import Self

from pydantic import Field, model_validator

from app.contracts import (
    ContractModel,
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
