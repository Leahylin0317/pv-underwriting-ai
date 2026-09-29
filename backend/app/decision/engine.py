from datetime import UTC, datetime
from typing import TypeVar

from app.contracts import (
    DecisionType,
    MaterialReviewAction,
    ProcessingStatus,
    UnderwritingCase,
    UnderwritingDecision,
)
from app.rules.explanations import explain_rules

Item = TypeVar("Item")


def unique_items(values: list[Item]) -> list[Item]:
    """保持原顺序并移除重复值。"""
    return list(dict.fromkeys(values))


class DecisionEngine:
    """按拒保优先的固定顺序汇总案件事实，不输出精算保费。"""

    MISSING_COORDINATES_RULE_ID = "REQ-PROJECT-COORDINATES"
    MISSING_COMPONENT_MODEL_RULE_ID = "REQ-COMPONENT-MODEL"
    PROVIDER_FAILURE_RULE_ID = "SYS-PROVIDER-FAILURE"
    INCOMPLETE_PACKAGE_RULE_ID = "PKG-MINIMUM-001"

    def decide(self, case: UnderwritingCase) -> UnderwritingDecision:
        rule_ids: list[str] = []
        reasons: list[str] = []
        missing_requirements: list[str] = []
        warnings: list[str] = []
        conditions: list[str] = []
        has_reject = False
        has_surcharge = False
        has_conditional = False
        has_manual_review = False
        has_request_more = False

        if case.project.project_type.value in {"unsupported", "unknown"}:
            has_manual_review = True
            reasons.append("无法确认标的属于屋顶式或车棚顶式光伏，需人工核实承保范围")

        if not case.materials and case.package_assessment is None:
            has_manual_review = True
            reasons.append("当前案件没有可审核的投保材料")

        if case.project.longitude is None or case.project.latitude is None:
            has_request_more = True
            rule_ids.append(self.MISSING_COORDINATES_RULE_ID)
            reasons.append("项目经纬度缺失，无法查询所在地气象风险")
            missing_requirements.append("补充项目准确经纬度")

        if not case.project.component_model:
            has_request_more = True
            rule_ids.append(self.MISSING_COMPONENT_MODEL_RULE_ID)
            reasons.append("组件型号缺失，无法查询组件抗灾参数")
            missing_requirements.append("补充光伏组件完整型号")

        if (
            case.package_assessment is not None
            and case.package_assessment.missing_requirements
        ):
            has_request_more = True
            rule_ids.append(self.INCOMPLETE_PACKAGE_RULE_ID)
            missing_requirements.extend(case.package_assessment.missing_requirements)
            reasons.append("投保材料包未达到赛题要求的最低材料和视角门槛")

        for review in case.material_reviews:
            if review.action is MaterialReviewAction.RECOMMEND_REJECT:
                has_reject = True
                rule_ids.extend(review.triggered_rule_ids)
                reasons.extend(review.reasons)
            elif review.action is MaterialReviewAction.REQUEST_MORE:
                has_request_more = True
                rule_ids.extend(review.triggered_rule_ids)
                reasons.extend(review.reasons)
                missing_requirements.extend(review.missing_requirements)
            elif review.action is MaterialReviewAction.SURCHARGE:
                has_surcharge = True
                rule_ids.extend(review.triggered_rule_ids)
                reasons.extend(review.reasons)
            elif review.action is MaterialReviewAction.CONDITIONAL:
                has_conditional = True
                rule_ids.extend(review.triggered_rule_ids)
                reasons.extend(review.reasons)
                conditions.extend(review.missing_requirements)
            elif review.action is MaterialReviewAction.WARNING:
                rule_ids.extend(review.triggered_rule_ids)
                reasons.extend(review.reasons)
            if review.requires_manual_review:
                has_manual_review = True

        assessment = case.catastrophe_assessment
        if assessment is not None:
            rule_ids.extend(assessment.triggered_rule_ids)
            reasons.append(assessment.explanation)
            warnings.extend(assessment.factors)
            has_manual_review = has_manual_review or assessment.requires_manual_review

        provider_failed = any(
            trace.status in {ProcessingStatus.PARTIAL, ProcessingStatus.FAILED}
            for trace in case.processing_trace
        )
        if provider_failed:
            warnings.append("部分自动识别服务未完整执行，需要人工检查处理留痕")
            has_manual_review = True
            rule_ids.append(self.PROVIDER_FAILURE_RULE_ID)
            reasons.append("自动识别服务未完整执行")

        # 明确的禁保事实必须保留在整案结论中，不能被其他材料缺失覆盖。
        if has_reject:
            decision = DecisionType.RECOMMEND_REJECT
        elif has_request_more:
            decision = DecisionType.REQUEST_MORE
        elif has_manual_review:
            decision = DecisionType.MANUAL_REVIEW
        elif has_surcharge:
            decision = DecisionType.SURCHARGE
        elif has_conditional:
            decision = DecisionType.CONDITIONAL_ACCEPT
        else:
            decision = DecisionType.ACCEPT
            if not reasons:
                reasons.append("材料完整，首期检查未发现拒保或待人工核实事项")

        return UnderwritingDecision(
            decision=decision,
            decisive_rule_ids=unique_items(rule_ids),
            rule_explanations=explain_rules(unique_items(rule_ids)),
            reasons=unique_items(reasons),
            conditions=unique_items(conditions),
            warnings=unique_items(warnings),
            missing_requirements=unique_items(missing_requirements),
            generated_at=datetime.now(UTC),
        )
