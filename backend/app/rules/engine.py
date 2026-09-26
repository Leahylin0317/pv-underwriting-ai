from app.contracts import (
    Material,
    MaterialQualityStatus,
    MaterialReview,
    MaterialReviewAction,
)


class RuleEngine:
    """第一阶段确定性核保规则引擎。"""

    MATERIAL_QUALITY_RULE_ID = "MAT-QUALITY-001"

    def evaluate_materials(
        self,
        materials: list[Material],
    ) -> list[MaterialReview]:
        return [self.evaluate_material(material) for material in materials]

    def evaluate_material(self, material: Material) -> MaterialReview:
        if material.quality_status is MaterialQualityStatus.USABLE:
            return MaterialReview(
                material_id=material.material_id,
                action=MaterialReviewAction.PASS,
                triggered_rule_ids=[],
                finding_ids=[],
                ocr_field_ids=[],
                reasons=["材料质量满足后续自动处理要求"],
                missing_requirements=[],
                requires_manual_review=False,
            )

        if material.quality_status is MaterialQualityStatus.POOR:
            reason = "材料质量较差，无法保证自动识别结果可靠"
        elif material.quality_status is MaterialQualityStatus.UNUSABLE:
            reason = "材料质量不可用，无法进行可靠识别"
        else:
            reason = "材料质量状态未知，无法确认是否满足识别要求"

        return MaterialReview(
            material_id=material.material_id,
            action=MaterialReviewAction.REQUEST_MORE,
            triggered_rule_ids=[self.MATERIAL_QUALITY_RULE_ID],
            finding_ids=[],
            ocr_field_ids=[],
            reasons=[reason],
            missing_requirements=["补充清晰、完整且包含关键区域的材料"],
            requires_manual_review=False,
        )