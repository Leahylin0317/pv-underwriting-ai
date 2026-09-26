from collections import Counter
from typing import Literal, Self

from pydantic import Field, model_validator

from .common import ContractModel
from .findings import RiskFinding
from .inputs import Material, OcrField, ProjectInfo
from .outputs import MaterialReview, ProcessingTrace, UnderwritingDecision
from .profiles import CatastropheAssessment, ComponentProfile, WeatherProfile


def find_duplicate_ids(values: list[str]) -> list[str]:
    """返回列表中重复出现的ID。"""

    return sorted(value for value, count in Counter(values).items() if count > 1)


class UnderwritingCase(ContractModel):
    """一次分布式光伏财产险智能核保案件。"""

    schema_version: Literal["0.1.0"]
    case_id: str = Field(min_length=1)
    project: ProjectInfo
    materials: list[Material]
    ocr_fields: list[OcrField]
    findings: list[RiskFinding]
    component_profile: ComponentProfile | None = None
    weather_profile: WeatherProfile | None = None
    catastrophe_assessment: CatastropheAssessment | None = None
    material_reviews: list[MaterialReview]
    decision: UnderwritingDecision | None = None
    processing_trace: list[ProcessingTrace]

    @model_validator(mode="after")
    def validate_ids_and_references(self) -> Self:
        material_ids = [material.material_id for material in self.materials]
        ocr_field_ids = [field.field_id for field in self.ocr_fields]
        finding_ids = [finding.finding_id for finding in self.findings]

        duplicate_material_ids = find_duplicate_ids(material_ids)
        duplicate_ocr_field_ids = find_duplicate_ids(ocr_field_ids)
        duplicate_finding_ids = find_duplicate_ids(finding_ids)

        if duplicate_material_ids:
            raise ValueError(f"duplicate material IDs: {duplicate_material_ids}")
        if duplicate_ocr_field_ids:
            raise ValueError(f"duplicate OCR field IDs: {duplicate_ocr_field_ids}")
        if duplicate_finding_ids:
            raise ValueError(f"duplicate finding IDs: {duplicate_finding_ids}")

        material_id_set = set(material_ids)
        ocr_field_id_set = set(ocr_field_ids)
        finding_id_set = set(finding_ids)

        for field in self.ocr_fields:
            if field.material_id not in material_id_set:
                raise ValueError(
                    f"OCR field {field.field_id} references unknown material "
                    f"{field.material_id}"
                )

        for finding in self.findings:
            if finding.material_id not in material_id_set:
                raise ValueError(
                    f"finding {finding.finding_id} references unknown material "
                    f"{finding.material_id}"
                )

        for review in self.material_reviews:
            if review.material_id not in material_id_set:
                raise ValueError(
                    f"material review references unknown material {review.material_id}"
                )

            unknown_finding_ids = sorted(set(review.finding_ids) - finding_id_set)
            if unknown_finding_ids:
                raise ValueError(
                    f"material review references unknown findings: {unknown_finding_ids}"
                )

            unknown_ocr_field_ids = sorted(
                set(review.ocr_field_ids) - ocr_field_id_set
            )
            if unknown_ocr_field_ids:
                raise ValueError(
                    "material review references unknown OCR fields: "
                    f"{unknown_ocr_field_ids}"
                )

        return self