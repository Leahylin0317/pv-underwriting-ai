from datetime import UTC, datetime
from typing import TypeVar

from app.contracts import (
    DecisionType,
    MaterialReviewAction,
    ProcessingStatus,
    UnderwritingCase,
    UnderwritingDecision,
)

Item = TypeVar("Item")


def unique_items(values: list[Item]) -> list[Item]:
    """保持原顺序并移除重复值。"""

    return list(dict.fromkeys(values))


class DecisionEngine:
    """在业务规则尚未全部确认时生成保守的整单决策。"""

    MISSING_COORDINATES_RULE_ID = "REQ-PROJECT-COORDINATES"
    MISSING_COMPONENT_MODEL_RULE_ID = "REQ-COMPONENT-MODEL"
    PROVIDER_FAILURE_RULE_ID = "SYS-PROVIDER-FAILURE"

    def decide(self, case: UnderwritingCase) -> UnderwritingDecision:
        rule_ids: list[str] = []
        reasons: list[str] = []
        missing_requirements: list[str] = []
        warnings: list[str] = []
        requires_more = False

        if case.project.longitude is None or case.project.latitude is None:
            requires_more = True
            rule_ids.append(self.MISSING_COORDINATES_RULE_ID)
            reasons.append("项目经纬度缺失，无法查询所在地气象风险")
            missing_requirements.append("补充项目准确经纬度")

        if case.project.component_model is None:
            requires_more = True
            rule_ids.append(self.MISSING_COMPONENT_MODEL_RULE_ID)
            reasons.append("组件型号缺失，无法查询组件抗灾参数")
            missing_requirements.append("补充光伏组件完整型号")

        for review in case.material_reviews:
            if review.action is MaterialReviewAction.REQUEST_MORE:
                requires_more = True
                rule_ids.extend(review.triggered_rule_ids)
                reasons.extend(review.reasons)
                missing_requirements.extend(review.missing_requirements)
            elif review.action is not MaterialReviewAction.PASS:
                reasons.extend(review.reasons)
                warnings.append(
                    f"材料 {review.material_id} 存在尚未自动处理的审核动作"
                )

        provider_failed = any(
            trace.status in {ProcessingStatus.PARTIAL, ProcessingStatus.FAILED}
            for trace in case.processing_trace
        )

        if provider_failed:
            warnings.append("部分自动识别服务未完整执行，需要人工检查处理留痕")

        if requires_more:
            decision = DecisionType.REQUEST_MORE
        else:
            decision = DecisionType.MANUAL_REVIEW
            if provider_failed:
                rule_ids.append(self.PROVIDER_FAILURE_RULE_ID)
                reasons.append("自动识别服务未完整执行")
            elif not reasons:
                reasons.append("业务核保规则尚未全部确认，当前转人工复核")

        return UnderwritingDecision(
            decision=decision,
            decisive_rule_ids=unique_items(rule_ids),
            reasons=unique_items(reasons),
            conditions=[],
            warnings=unique_items(warnings),
            missing_requirements=unique_items(missing_requirements),
            generated_at=datetime.now(UTC),
        )