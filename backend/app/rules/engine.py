from typing import ClassVar

from app.contracts import (
    CaptureView,
    DetectionStatus,
    EnvironmentRelation,
    Material,
    MaterialCategory,
    MaterialQualityStatus,
    MaterialReview,
    MaterialReviewAction,
    OcrField,
    OcrValueStatus,
    PackageAssessment,
    ProjectInfo,
    ProjectType,
    RiskCategory,
    RiskFinding,
    WatermarkStatus,
)

from .config import BusinessRulesConfig

REJECT_ENVIRONMENT_CATEGORIES = frozenset(
    {
        RiskCategory.AGRICULTURE_ENVIRONMENT,
        RiskCategory.FOREST_ENVIRONMENT,
        RiskCategory.LIVESTOCK_ENVIRONMENT,
        RiskCategory.FISHERY_ENVIRONMENT,
        RiskCategory.WATER_ADJACENT_ENVIRONMENT,
        RiskCategory.TIDAL_FLAT_ENVIRONMENT,
        RiskCategory.MOUNTAIN_ENVIRONMENT,
        RiskCategory.DESERTIFICATION_ENVIRONMENT,
    }
)

CRITICAL_ENVIRONMENT_CHECKS = REJECT_ENVIRONMENT_CATEGORIES
SUPPLEMENT_REQUIRED_CHECKS = frozenset({RiskCategory.IMAGE_QUALITY})
REQUIRED_MATERIAL_CATEGORIES = (
    MaterialCategory.ROOF_CONNECTION,
    MaterialCategory.PARAPET,
    MaterialCategory.WORKSHOP,
    MaterialCategory.GRID_CONNECTION_DOCUMENT,
    MaterialCategory.ELECTRICAL_GROUNDING,
    MaterialCategory.COMPONENT_NAMEPLATE,
    MaterialCategory.INVERTER_NAMEPLATE,
    MaterialCategory.COMBINER_BOX,
)
EXPECTED_CHECKS_BY_MATERIAL = {
    MaterialCategory.PANORAMA: CRITICAL_ENVIRONMENT_CHECKS
    | frozenset(
        {
            RiskCategory.IMAGE_QUALITY,
            RiskCategory.SEVERE_SHADING,
            RiskCategory.MINOR_SHADING,
            RiskCategory.AISLE_OBSTRUCTION,
        }
    ),
    MaterialCategory.ROOF_CONNECTION: frozenset(
        {
            RiskCategory.INSTALLATION_TYPE,
            RiskCategory.AISLE_OBSTRUCTION,
            RiskCategory.ROOF_CONNECTION_ABNORMAL,
        }
        | SUPPLEMENT_REQUIRED_CHECKS
    ),
    MaterialCategory.PARAPET: frozenset(
        {RiskCategory.MISSING_PARAPET_OR_GUARDRAIL}
    ) | SUPPLEMENT_REQUIRED_CHECKS,
    MaterialCategory.WORKSHOP: frozenset(
        {RiskCategory.FLAMMABLE_MATERIAL, RiskCategory.HAZARDOUS_MATERIAL}
    ) | SUPPLEMENT_REQUIRED_CHECKS,
    MaterialCategory.COMBINER_BOX: frozenset(
        {
            RiskCategory.COMBINER_BOX_SEAL_ABNORMAL,
            RiskCategory.COMBINER_BOX_FUSE_ABNORMAL,
            RiskCategory.SURGE_PROTECTOR_ABNORMAL,
        }
    ) | SUPPLEMENT_REQUIRED_CHECKS,
    MaterialCategory.ELECTRICAL_GROUNDING: frozenset(
        {
            RiskCategory.ELECTRICAL_GROUNDING_ABNORMAL,
        }
    ) | SUPPLEMENT_REQUIRED_CHECKS,
    MaterialCategory.COMPONENT_NAMEPLATE: SUPPLEMENT_REQUIRED_CHECKS,
    MaterialCategory.INVERTER_NAMEPLATE: frozenset(
        {RiskCategory.INVERTER_ABNORMAL}
    ) | SUPPLEMENT_REQUIRED_CHECKS,
    MaterialCategory.COMPONENT_SURFACE: frozenset(
        {
            RiskCategory.MODULE_DAMAGE,
        }
    ) | SUPPLEMENT_REQUIRED_CHECKS,
    MaterialCategory.MONITORING_OPTIONAL: frozenset(
        {RiskCategory.MONITORING_EFFECTIVE_COVERAGE}
    ) | SUPPLEMENT_REQUIRED_CHECKS,
    MaterialCategory.OTHER: SUPPLEMENT_REQUIRED_CHECKS,
}
ADVANCED_CHECKS_BY_MATERIAL = {
    MaterialCategory.PARAPET: frozenset({RiskCategory.DRAINAGE_ABNORMAL}),
    MaterialCategory.ROOF_CONNECTION: frozenset(
        {
            RiskCategory.SUPPORT_CORROSION,
            RiskCategory.SUPPORT_DEFORMATION,
            RiskCategory.WATERPROOF_LAYER_DAMAGE,
        }
    ),
    MaterialCategory.WORKSHOP: frozenset(
        {
            RiskCategory.DANGEROUS_PROCESS,
            RiskCategory.CLEANROOM,
            RiskCategory.FIRE_PROTECTION_ABSENT,
        }
    ),
    MaterialCategory.ELECTRICAL_GROUNDING: frozenset(
        {RiskCategory.UNPROTECTED_CABLE}
    ),
    MaterialCategory.COMPONENT_SURFACE: frozenset(
        {RiskCategory.MODULE_BACKSHEET_BULGING, RiskCategory.MODULE_DISCOLORATION}
    ),
}
PROHIBITED_PROJECT_TERMS = ("集中式", "林光", "渔光", "滩涂")
OCR_MIN_CONFIDENCE = 0.65
RISK_CATEGORY_LABELS = {
    RiskCategory.AGRICULTURE_ENVIRONMENT: "农业环境",
    RiskCategory.FOREST_ENVIRONMENT: "林地环境",
    RiskCategory.LIVESTOCK_ENVIRONMENT: "畜牧环境",
    RiskCategory.FISHERY_ENVIRONMENT: "渔业环境",
    RiskCategory.WATER_ADJACENT_ENVIRONMENT: "涉水环境",
    RiskCategory.TIDAL_FLAT_ENVIRONMENT: "滩涂环境",
    RiskCategory.MOUNTAIN_ENVIRONMENT: "山地环境",
    RiskCategory.DESERTIFICATION_ENVIRONMENT: "沙化环境",
    RiskCategory.IMAGE_QUALITY: "图片清晰度",
    RiskCategory.SEVERE_SHADING: "严重遮挡",
    RiskCategory.MINOR_SHADING: "轻微遮挡",
    RiskCategory.AISLE_OBSTRUCTION: "检修通道阻塞",
    RiskCategory.INSTALLATION_TYPE: "安装类型",
    RiskCategory.ROOF_CONNECTION_ABNORMAL: "屋顶连接异常",
    RiskCategory.MISSING_PARAPET_OR_GUARDRAIL: "女儿墙或护栏缺失",
    RiskCategory.DRAINAGE_ABNORMAL: "排水异常",
    RiskCategory.FLAMMABLE_MATERIAL: "易燃物",
    RiskCategory.HAZARDOUS_MATERIAL: "危险品",
    RiskCategory.MODULE_DAMAGE: "组件可见破损",
    RiskCategory.INVERTER_ABNORMAL: "逆变器可见异常",
    RiskCategory.ELECTRICAL_GROUNDING_ABNORMAL: "接地外观异常",
    RiskCategory.COMBINER_BOX_SEAL_ABNORMAL: "汇流箱密封异常",
    RiskCategory.COMBINER_BOX_FUSE_ABNORMAL: "汇流箱熔断器异常",
    RiskCategory.SURGE_PROTECTOR_ABNORMAL: "浪涌保护器异常",
    RiskCategory.MONITORING_EFFECTIVE_COVERAGE: "监控有效覆盖",
    RiskCategory.UNPROTECTED_CABLE: "线缆裸露且无保护",
    RiskCategory.MODULE_BACKSHEET_BULGING: "组件背板鼓包",
    RiskCategory.MODULE_DISCOLORATION: "组件变色",
    RiskCategory.SUPPORT_CORROSION: "支架锈蚀",
    RiskCategory.SUPPORT_DEFORMATION: "支架变形",
    RiskCategory.WATERPROOF_LAYER_DAMAGE: "防水层损坏",
    RiskCategory.DANGEROUS_PROCESS: "危险工艺",
    RiskCategory.CLEANROOM: "洁净车间",
    RiskCategory.FIRE_PROTECTION_ABSENT: "消防设施缺失或异常",
}
ENVIRONMENT_RELATION_DESCRIPTIONS = {
    EnvironmentRelation.PROJECT_SITE: "项目现场本身",
    EnvironmentRelation.OPERATIONAL_SURROUNDINGS: "项目邻近周边",
    EnvironmentRelation.DISTANT_BACKGROUND: "远处背景景物",
    EnvironmentRelation.UNCERTAIN: "现场关系不确定",
}


def _normalized_text(value: str | None) -> str:
    if value is None:
        return ""
    return "".join(value.casefold().split()).replace("，", ",")


class RuleEngine:
    """将可追溯的 OCR 和视觉事实映射为首期核保动作。

    规则编号和动作是比赛首期的保守建议；费率和承保授权仍由业务确认。
    """

    MATERIAL_QUALITY_RULE_ID = "MAT-QUALITY-001"
    PACKAGE_MINIMUM_RULE_ID = "PKG-MINIMUM-001"
    ENVIRONMENT_REJECT_RULE_ID = "ENV-EXCLUDED-001"
    ENVIRONMENT_COVERAGE_RULE_ID = "ENV-COVERAGE-001"
    ENVIRONMENT_RELATION_REVIEW_RULE_ID = "ENV-SITE-RELATION-REVIEW-001"
    ENVIRONMENT_BACKGROUND_RULE_ID = "ENV-BACKGROUND-CONTEXT-001"
    FILING_PROHIBITED_RULE_ID = "DOC-FILING-EXCLUDED-001"
    CROSS_CHECK_RULE_ID = "DOC-CROSS-CHECK-001"
    WATERMARK_RULE_ID = "IMG-WATERMARK-001"
    WATERMARK_DATE_RULE_ID = "IMG-WATERMARK-DATE-001"
    FINDING_WARNING_RULE_ID = "IMG-FINDING-WARNING-001"
    SEVERE_SHADING_RULE_ID = "IMG-SHADING-SEVERE-001"

    _ACTION_PRIORITY: ClassVar[dict[MaterialReviewAction, int]] = {
        MaterialReviewAction.PASS: 0,
        MaterialReviewAction.NOT_APPLICABLE: 0,
        MaterialReviewAction.WARNING: 1,
        MaterialReviewAction.CONDITIONAL: 2,
        MaterialReviewAction.SURCHARGE: 3,
        MaterialReviewAction.REQUEST_MORE: 4,
        MaterialReviewAction.RECOMMEND_REJECT: 5,
    }

    def __init__(self, config: BusinessRulesConfig | None = None) -> None:
        self.config = config or BusinessRulesConfig.load()

    def _expected_checks_for_material(
        self,
        category: MaterialCategory,
    ) -> frozenset[RiskCategory] | None:
        expected = EXPECTED_CHECKS_BY_MATERIAL.get(category)
        if expected is None:
            return None
        if self.config.advanced_checks_enabled:
            expected |= ADVANCED_CHECKS_BY_MATERIAL.get(category, frozenset())
        return expected

    def assess_package(
        self,
        materials: list[Material],
        *,
        project_type: ProjectType | None = None,
    ) -> PackageAssessment:
        document_categories = {
            MaterialCategory.FILING_CERTIFICATE,
            MaterialCategory.GRID_CONNECTION_DOCUMENT,
            MaterialCategory.PROJECT_DOCUMENT,
            MaterialCategory.EQUIPMENT_INVENTORY,
        }
        images = [
            item
            for item in materials
            if item.media_type in {"image/jpeg", "image/png"}
            and item.category not in document_categories
        ]
        panoramas = [
            item
            for item in materials
            if item.category is MaterialCategory.PANORAMA
            and item.media_type in {"image/jpeg", "image/png"}
        ]
        has_filing_certificate = any(
            item.category is MaterialCategory.FILING_CERTIFICATE for item in materials
        )
        has_front = any(item.capture_view is CaptureView.FRONT_LEVEL for item in panoramas)
        has_overhead = any(item.capture_view is CaptureView.OVERHEAD for item in panoramas)
        supplied_categories = {item.category for item in materials}
        required_categories = (
            category
            for category in REQUIRED_MATERIAL_CATEGORIES
            if not (
                project_type is ProjectType.CARPORT
                and category is MaterialCategory.WORKSHOP
            )
        )
        missing_categories = [
            category.value
            for category in required_categories
            if category not in supplied_categories
        ]
        missing: list[str] = []

        if len(images) < 5:
            missing.append(f"至少提交5张图片材料（当前{len(images)}张）")
        if len(panoramas) < 2:
            missing.append(f"至少提交2张电站全景照（当前{len(panoramas)}张）")
        if not has_filing_certificate:
            missing.append("补充电站备案证")
        if panoramas and not has_front:
            missing.append("标注或补拍一张正面平视全景照")
        if panoramas and not has_overhead:
            missing.append("标注或补拍一张俯拍全景照")

        minimum_gate_passed = not missing
        coverage_requirements = [
            self._material_category_label(item) for item in missing_categories
        ]
        if self.config.package_requirement_profile == "full_intake" and missing_categories:
            missing.append("补充完整投保清单中的材料类别：" + "、".join(coverage_requirements))

        return PackageAssessment(
            image_count=len(images),
            panorama_count=len(panoramas),
            has_filing_certificate=has_filing_certificate,
            has_front_level_panorama=has_front,
            has_overhead_panorama=has_overhead,
            missing_material_categories=missing_categories,
            missing_requirements=missing,
            requirement_profile=self.config.package_requirement_profile,
            minimum_gate_passed=minimum_gate_passed,
            document_image_count=sum(
                item.media_type in {"image/jpeg", "image/png"}
                and item.category in document_categories for item in materials
            ),
            coverage_requirements=coverage_requirements,
        )

    def evaluate_materials(
        self,
        materials: list[Material],
        *,
        findings: list[RiskFinding] | None = None,
        ocr_fields: list[OcrField] | None = None,
        project: ProjectInfo | None = None,
    ) -> list[MaterialReview]:
        findings = findings or []
        ocr_fields = ocr_fields or []
        by_material_findings: dict[str, list[RiskFinding]] = {}
        by_material_fields: dict[str, list[OcrField]] = {}
        for finding in findings:
            by_material_findings.setdefault(finding.material_id, []).append(finding)
        for field in ocr_fields:
            by_material_fields.setdefault(field.material_id, []).append(field)

        reviews: list[MaterialReview] = []
        for material in materials:
            reviews.append(
                self.evaluate_material(
                    material,
                    findings=by_material_findings.get(material.material_id, []),
                    ocr_fields=by_material_fields.get(material.material_id, []),
                    project=project,
                )
            )

        reviews = self._apply_panorama_coverage(reviews, materials, findings)

        for review_index, material in enumerate(materials):
            if material.category is not MaterialCategory.WORKSHOP or project is None:
                continue
            review = reviews[review_index]
            reasons = [*review.reasons]
            missing = [*review.missing_requirements]
            rule_ids = [*review.triggered_rule_ids]
            actions = [review.action]
            requires_manual = review.requires_manual_review
            if not self.config.high_fire_risk_industries:
                rule_ids.append("INDUSTRY-FIRE-RULES-UNCONFIGURED-001")
            if project.industry_name is None or not project.industry_name.strip():
                actions.append(MaterialReviewAction.REQUEST_MORE)
                reasons.append("未提供企业所属行业，无法判定是否命中高火险行业规则")
                missing.append("补充企业所属行业，并由核保人员核验高火险行业规则")
                requires_manual = True
            elif not self.config.high_fire_risk_industries:
                rule_ids.append("INDUSTRY-FIRE-RULES-UNCONFIGURED-001")
                actions.append(MaterialReviewAction.WARNING)
                reasons.append(
                    f"申报行业为“{project.industry_name.strip()}”；正式高火险行业清单尚未配置，需人工核验"
                )
                requires_manual = True
            else:
                industry = _normalized_text(project.industry_name)
                matches = [
                    item
                    for item in self.config.high_fire_risk_industries
                    if _normalized_text(item) in industry
                ]
                if matches and project.fire_surcharge_confirmed is not True:
                    actions.append(MaterialReviewAction.REQUEST_MORE)
                    reasons.append(
                        "企业所属行业命中高火险行业清单；尚未确认已按正式规则加费，需补充加费方案并由核保人员核验"
                    )
                    missing.append("确认高火险行业加费已执行，并提交加费依据")
                    requires_manual = True
                elif matches:
                    actions.append(MaterialReviewAction.WARNING)
                    reasons.append(
                        "企业所属行业命中高火险行业清单且已申报加费；加费比例与承保条件仍须按正式业务规则核验"
                    )
                    requires_manual = True
            reviews[review_index] = review.model_copy(
                update={
                    "action": max(actions, key=self._ACTION_PRIORITY.__getitem__),
                    "triggered_rule_ids": list(dict.fromkeys(rule_ids)),
                    "reasons": list(dict.fromkeys(reasons)),
                    "missing_requirements": list(dict.fromkeys(missing)),
                    "requires_manual_review": requires_manual,
                }
            )

        if project is not None:
            reviews = self._apply_filing_cross_checks(
                reviews,
                materials,
                ocr_fields,
                project,
            )
        return reviews

    def evaluate_material(
        self,
        material: Material,
        *,
        findings: list[RiskFinding] | None = None,
        ocr_fields: list[OcrField] | None = None,
        project: ProjectInfo | None = None,
    ) -> MaterialReview:
        findings = findings or []
        ocr_fields = ocr_fields or []
        rule_ids: list[str] = []
        reasons: list[str] = []
        missing: list[str] = []
        finding_ids: list[str] = []
        ocr_field_ids = [item.field_id for item in ocr_fields]
        actions: list[MaterialReviewAction] = []
        manual_review = False
        relevant_checks = self._expected_checks_for_material(material.category) or frozenset()
        relevant_categories = relevant_checks | {RiskCategory.IMAGE_QUALITY}
        if material.category in {
            MaterialCategory.PANORAMA,
            MaterialCategory.ROOF_CONNECTION,
        }:
            # The challenge requires excluded surroundings to be assessed from
            # site panoramas and whenever they are directly visible at the roof
            # connection. Other material types must not inherit these findings.
            relevant_categories |= CRITICAL_ENVIRONMENT_CHECKS

        if material.quality_status is not MaterialQualityStatus.USABLE:
            rule_ids.append(self.MATERIAL_QUALITY_RULE_ID)
            actions.append(MaterialReviewAction.REQUEST_MORE)
            reasons.append(self._quality_reason(material.quality_status))
            if material.quality_issues:
                reasons.append(
                    "文件预检质量标记：" + "、".join(material.quality_issues)
                )
            missing.append("补充清晰、完整且包含关键区域的材料")

        for finding in findings:
            if finding.category not in relevant_categories:
                continue
            if finding.detection_status is DetectionStatus.NOT_APPLICABLE:
                continue
            if finding.detection_status is DetectionStatus.NOT_DETECTED:
                if finding.requires_manual_review:
                    finding_ids.append(finding.finding_id)
                    rule_ids.append(self.FINDING_WARNING_RULE_ID)
                    actions.append(MaterialReviewAction.WARNING)
                    reasons.append(f"模型标记该检查需人工复核：{finding.label}；{finding.evidence_text}")
                    manual_review = True
                continue

            finding_ids.append(finding.finding_id)
            if finding.detection_status is DetectionStatus.UNCERTAIN:
                if finding.category in SUPPLEMENT_REQUIRED_CHECKS:
                    rule_ids.append(self.MATERIAL_QUALITY_RULE_ID)
                    actions.append(MaterialReviewAction.REQUEST_MORE)
                    reasons.append(f"无法确认图片质量是否足以支持判断：{finding.evidence_text}")
                    missing.append("补拍光线充足、清晰且完整展示检查区域的照片")
                    manual_review = True
                elif finding.category in CRITICAL_ENVIRONMENT_CHECKS:
                    actions.append(MaterialReviewAction.WARNING)
                    if finding.environment_relation is EnvironmentRelation.DISTANT_BACKGROUND:
                        rule_ids.append(self.ENVIRONMENT_BACKGROUND_RULE_ID)
                        reasons.append(
                            f"环境识别状态不确定，但其位置关系被标记为远处背景；"
                            f"不作为项目现场拒保事实：{finding.label}；{finding.evidence_text}"
                        )
                    else:
                        rule_ids.append(self.ENVIRONMENT_RELATION_REVIEW_RULE_ID)
                        reasons.append(
                            f"拒保环境或其与项目现场的关系尚不确定，暂不自动拒保；"
                            f"由核保人员结合原图确认：{finding.label}；{finding.evidence_text}"
                        )
                        manual_review = True
                else:
                    rule_ids.append(self.FINDING_WARNING_RULE_ID)
                    actions.append(MaterialReviewAction.WARNING)
                    reasons.append(f"图片风险判断不确定：{finding.label}；{finding.evidence_text}")
                    manual_review = True
                continue

            if finding.category in REJECT_ENVIRONMENT_CATEGORIES:
                if finding.environment_relation is EnvironmentRelation.DISTANT_BACKGROUND:
                    rule_ids.append(self.ENVIRONMENT_BACKGROUND_RULE_ID)
                    actions.append(MaterialReviewAction.WARNING)
                    reasons.append(
                        f"识别到的{finding.label}属于远处背景景物，不作为项目现场拒保事实；"
                        f"证据：{finding.evidence_text}"
                    )
                    continue

                auto_reject_eligible = (
                    finding.environment_relation
                    in self.config.environment_auto_reject_relations
                    and finding.confidence
                    >= self.config.environment_auto_reject_min_confidence
                    and not finding.requires_manual_review
                )
                if not auto_reject_eligible:
                    rule_ids.append(self.ENVIRONMENT_RELATION_REVIEW_RULE_ID)
                    actions.append(MaterialReviewAction.WARNING)
                    manual_review = True
                    relation_reasons = []
                    if finding.requires_manual_review:
                        relation_reasons.append("模型明确要求人工复核")
                    if (
                        finding.environment_relation
                        not in self.config.environment_auto_reject_relations
                    ):
                        if finding.environment_relation is EnvironmentRelation.OPERATIONAL_SURROUNDINGS:
                            relation_reasons.append(
                                "识别对象位于项目邻近周边，适用边界尚待业务确认"
                            )
                        else:
                            relation_reasons.append(
                                "无法确认该环境是否属于项目现场"
                            )
                    if (
                        finding.confidence
                        < self.config.environment_auto_reject_min_confidence
                    ):
                        relation_reasons.append(
                            f"模型参考置信度{finding.confidence:.2f}低于当前配置门槛"
                            f"{self.config.environment_auto_reject_min_confidence:.2f}"
                        )
                    reasons.append(
                        f"{'；'.join(relation_reasons)}，保留风险证据并转人工核验，不自动拒保："
                        f"{finding.label}；{finding.evidence_text}"
                    )
                    continue

                rule_ids.append(self.ENVIRONMENT_REJECT_RULE_ID)
                actions.append(MaterialReviewAction.RECOMMEND_REJECT)
                relation_description = ENVIRONMENT_RELATION_DESCRIPTIONS[
                    finding.environment_relation
                ]
                reasons.append(
                    f"高风险环境被识别为{relation_description}，模型参考置信度"
                    f"{finding.confidence:.2f}达到当前配置门槛"
                    f"{self.config.environment_auto_reject_min_confidence:.2f}，且未要求人工复核；"
                    f"触发拒保环境规则："
                    f"{finding.label}；{finding.evidence_text}"
                )
                continue

            if finding.requires_manual_review:
                rule_ids.append(self.FINDING_WARNING_RULE_ID)
                actions.append(MaterialReviewAction.WARNING)
                reasons.append(f"模型要求人工复核：{finding.label}；{finding.evidence_text}")
                manual_review = True

            if finding.category is RiskCategory.IMAGE_QUALITY:
                rule_ids.append(self.MATERIAL_QUALITY_RULE_ID)
                actions.append(MaterialReviewAction.REQUEST_MORE)
                reasons.append(f"图片质量不足，无法可靠检查：{finding.evidence_text}")
                missing.append("补拍光线充足、清晰且完整展示检查区域的照片")
                continue

            if finding.category is RiskCategory.SEVERE_SHADING:
                if finding.requires_manual_review:
                    reasons.append(
                        f"模型要求人工复核严重遮挡候选；自动流程保留图片证据，不直接拒保："
                        f"{finding.label}；{finding.evidence_text}"
                    )
                    manual_review = True
                    continue
                rule_ids.append(self.SEVERE_SHADING_RULE_ID)
                actions.append(MaterialReviewAction.RECOMMEND_REJECT)
                reasons.append(f"发现大面积遮挡：{finding.label}；{finding.evidence_text}")
                continue

            if finding.category is RiskCategory.UNPROTECTED_CABLE:
                if finding.requires_manual_review:
                    reasons.append(
                        f"模型要求人工复核裸露电缆候选；自动流程保留图片证据，不直接拒保："
                        f"{finding.label}；{finding.evidence_text}"
                    )
                    manual_review = True
                    continue
                rule_ids.append("ELEC-UNPROTECTED-CABLE-REJECT-001")
                actions.append(MaterialReviewAction.RECOMMEND_REJECT)
                reasons.append(
                    f"发现裸露且无保护的电缆，按赛题中期规则建议拒保："
                    f"{finding.label}；{finding.evidence_text}"
                )
                continue

            if finding.category is RiskCategory.MONITORING_EFFECTIVE_COVERAGE:
                rule_ids.append("DISC-MONITORING-REVIEW-001")
                actions.append(MaterialReviewAction.WARNING)
                reasons.append(
                    "已识别监控覆盖证据，列为优惠候选；须按正式监控条款人工核验覆盖范围、"
                    "在线状态及优惠条件"
                )
                manual_review = True
                continue

            if finding.category is RiskCategory.INSTALLATION_TYPE:
                if project is not None and not self._installation_matches(
                    f"{finding.label} {finding.evidence_text}", project
                ):
                    rule_ids.append(self.CROSS_CHECK_RULE_ID)
                    actions.append(MaterialReviewAction.WARNING)
                    reasons.append(
                        f"照片识别的安装类型“{finding.label}”与录入类型"
                        f"“{project.installation_type.value}”不一致，需核对"
                    )
                    manual_review = True
                continue

            if finding.category in {
                RiskCategory.MINOR_SHADING,
                RiskCategory.AISLE_OBSTRUCTION,
                RiskCategory.MISSING_PARAPET_OR_GUARDRAIL,
                RiskCategory.DRAINAGE_ABNORMAL,
                RiskCategory.FLAMMABLE_MATERIAL,
                RiskCategory.HAZARDOUS_MATERIAL,
                RiskCategory.COMBINER_BOX_SEAL_ABNORMAL,
                RiskCategory.COMBINER_BOX_FUSE_ABNORMAL,
                RiskCategory.SURGE_PROTECTOR_ABNORMAL,
                RiskCategory.ROOF_CONNECTION_ABNORMAL,
                RiskCategory.MODULE_DAMAGE,
                RiskCategory.INVERTER_ABNORMAL,
                RiskCategory.ELECTRICAL_GROUNDING_ABNORMAL,
                RiskCategory.MODULE_BACKSHEET_BULGING,
                RiskCategory.MODULE_DISCOLORATION,
                RiskCategory.SUPPORT_CORROSION,
                RiskCategory.SUPPORT_DEFORMATION,
                RiskCategory.WATERPROOF_LAYER_DAMAGE,
                RiskCategory.DANGEROUS_PROCESS,
                RiskCategory.CLEANROOM,
                RiskCategory.FIRE_PROTECTION_ABSENT,
            }:
                rule_ids.append(self.FINDING_WARNING_RULE_ID)
                actions.append(MaterialReviewAction.WARNING)
                reasons.append(f"发现待核保人确认的风险：{finding.label}；{finding.evidence_text}")
                manual_review = True

        if (
            material.category is not MaterialCategory.PANORAMA
            and self._expected_checks_for_material(material.category) is not None
            and material.media_type in {"image/jpeg", "image/png"}
        ):
            covered = {
                item.category
                for item in findings
                if item.detection_status is not DetectionStatus.NOT_APPLICABLE
            }
            expected = self._expected_checks_for_material(material.category)
            uncovered = (expected or frozenset()) - covered
            if uncovered:
                rule_ids.append(self.ENVIRONMENT_COVERAGE_RULE_ID)
                actions.append(MaterialReviewAction.REQUEST_MORE)
                names = "、".join(
                    sorted(RISK_CATEGORY_LABELS.get(item, item.value) for item in uncovered)
                )
                reasons.append(f"该类材料缺少以下检查项的明确状态：{names}")
                missing.append("补充清晰材料或完成未覆盖项目的人工检查：" + names)
                manual_review = True

        if material.category in {MaterialCategory.FILING_CERTIFICATE, MaterialCategory.PROJECT_DOCUMENT}:
            self._require_ocr_fields(
                ocr_fields,
                (("project_name", "site_address", "insured_name", "document_type") if material.category is MaterialCategory.PROJECT_DOCUMENT else ("project_name", "site_address", "insured_name")),
                rule_ids,
                reasons,
                missing,
                actions,
            )
        elif material.category is MaterialCategory.EQUIPMENT_INVENTORY and material.media_type in {"image/jpeg", "image/png", "application/pdf"}:
            self._require_ocr_fields(ocr_fields, ("row_1_equipment_name",), rule_ids, reasons, missing, actions)
        elif material.category is MaterialCategory.COMPONENT_NAMEPLATE:
            self._require_ocr_fields(
                ocr_fields,
                ("component_model", "rated_power_w", "serial_number"),
                rule_ids,
                reasons,
                missing,
                actions,
            )
        elif material.category is MaterialCategory.INVERTER_NAMEPLATE:
            self._require_ocr_fields(
                ocr_fields,
                ("inverter_model", "rated_power_w", "serial_number"),
                rule_ids,
                reasons,
                missing,
                actions,
            )
        elif material.category is MaterialCategory.GRID_CONNECTION_DOCUMENT:
            self._require_ocr_fields(
                ocr_fields,
                ("project_name", "project_entity", "site_address", "grid_connection_date"),
                rule_ids,
                reasons,
                missing,
                actions,
            )
        elif (
            material.category is MaterialCategory.ELECTRICAL_GROUNDING
            and material.media_type == "application/pdf"
        ):
            self._require_ocr_fields(
                ocr_fields,
                ("grounding_resistance_ohm", "inspection_date", "inspection_result"),
                rule_ids,
                reasons,
                missing,
                actions,
            )
        elif material.category is MaterialCategory.COMBINER_BOX:
            self._require_ocr_fields(
                ocr_fields,
                ("combiner_box_model", "rated_voltage_v", "rated_current_a", "serial_number"),
                rule_ids,
                reasons,
                missing,
                actions,
            )

        if material.category is MaterialCategory.MONITORING_OPTIONAL:
            monitoring_field = next(
                (
                    item
                    for item in ocr_fields
                    if item.field_name == "monitoring_present"
                    and item.value_status is OcrValueStatus.EXTRACTED
                    and item.confidence >= OCR_MIN_CONFIDENCE
                ),
                None,
            )
            monitoring_value = (
                (monitoring_field.normalized_value or monitoring_field.raw_value or "")
                .strip()
                .casefold()
                if monitoring_field is not None
                else ""
            )
            if monitoring_value in {"true", "yes", "present", "有", "是", "online", "运行"}:
                rule_ids.append("DISC-MONITORING-REVIEW-001")
                actions.append(MaterialReviewAction.WARNING)
                reasons.append("已提交监控材料；是否符合优惠条件需按正式条款人工核验，本系统不推定折扣")
                manual_review = True
            elif monitoring_value not in {"false", "no", "absent", "无", "否", "offline", "未运行"}:
                rule_ids.append("DISC-MONITORING-REVIEW-001")
                actions.append(MaterialReviewAction.WARNING)
                reasons.append("监控材料未能证明系统存在且正常运行，优惠资格需人工核实")
                manual_review = True

        if (
            material.category is MaterialCategory.PANORAMA
            and material.media_type in {"image/jpeg", "image/png"}
        ):
            if material.watermark_status is not WatermarkStatus.PRESENT:
                rule_ids.append(self.WATERMARK_RULE_ID)
                actions.append(MaterialReviewAction.WARNING)
                reasons.append("未能确认照片含有日期及经纬度水印，建议补充带水印的现场照片")
            else:
                missing_watermark_fields = []
                if material.captured_at is None:
                    missing_watermark_fields.append("拍摄日期")
                if material.longitude is None or material.latitude is None:
                    missing_watermark_fields.append("经纬度")
                if missing_watermark_fields:
                    rule_ids.append(self.WATERMARK_DATE_RULE_ID)
                    actions.append(MaterialReviewAction.REQUEST_MORE)
                    reasons.append("水印已识别，但关键水印字段无法完整读取")
                    missing.append("补充清晰水印信息：" + "、".join(missing_watermark_fields))
                elif project is None or project.proposed_start_date is None:
                    rule_ids.append(self.WATERMARK_DATE_RULE_ID)
                    actions.append(MaterialReviewAction.REQUEST_MORE)
                    reasons.append("已识别水印日期，但缺少拟起保日期，无法执行15日时效校验")
                    missing.append("补充拟起保日期以校验全景照拍摄时间")
                elif not (
                    0
                    <= (project.proposed_start_date - material.captured_at.date()).days
                    <= 15
                ):
                    rule_ids.append(self.WATERMARK_DATE_RULE_ID)
                    actions.append(MaterialReviewAction.REQUEST_MORE)
                    reasons.append("全景照拍摄日期不在拟起保日前15日内")
                    missing.append("补拍拟起保日前15日内的全景照片")

        if not actions:
            actions.append(MaterialReviewAction.PASS)
            reasons.append("材料检查未发现需要自动升级处理的事项")

        action = max(actions, key=self._ACTION_PRIORITY.__getitem__)
        return MaterialReview(
            material_id=material.material_id,
            action=action,
            triggered_rule_ids=list(dict.fromkeys(rule_ids)),
            finding_ids=list(dict.fromkeys(finding_ids)),
            ocr_field_ids=ocr_field_ids,
            reasons=list(dict.fromkeys(reasons)),
            missing_requirements=list(dict.fromkeys(missing)),
            requires_manual_review=manual_review,
        )

    def _apply_panorama_coverage(
        self,
        reviews: list[MaterialReview],
        materials: list[Material],
        findings: list[RiskFinding],
    ) -> list[MaterialReview]:
        """Aggregate checks across complementary panorama views in one case."""
        panorama_ids = {
            item.material_id
            for item in materials
            if item.category is MaterialCategory.PANORAMA
            and item.media_type in {"image/jpeg", "image/png"}
        }
        if not panorama_ids:
            return reviews

        expected = EXPECTED_CHECKS_BY_MATERIAL[MaterialCategory.PANORAMA]
        covered = {
            item.category
            for item in findings
            if item.material_id in panorama_ids
            and item.detection_status is not DetectionStatus.NOT_APPLICABLE
        }
        uncovered = expected - covered
        if not uncovered:
            return reviews

        target_index = next(
            index
            for index, material in enumerate(materials)
            if material.material_id in panorama_ids
        )
        review = reviews[target_index]
        names = "、".join(
            sorted(RISK_CATEGORY_LABELS.get(item, item.value) for item in uncovered)
        )
        reasons = [
            *review.reasons,
            f"合并检查{len(panorama_ids)}张全景后，以下检查项仍没有明确结果：{names}",
        ]
        missing = [
            *review.missing_requirements,
            "补充能覆盖未检查项目的全景视角，或由核保人员记录检查结果：" + names,
        ]
        reviews[target_index] = review.model_copy(
            update={
                "action": max(
                    [review.action, MaterialReviewAction.REQUEST_MORE],
                    key=self._ACTION_PRIORITY.__getitem__,
                ),
                "triggered_rule_ids": list(
                    dict.fromkeys(
                        [*review.triggered_rule_ids, self.ENVIRONMENT_COVERAGE_RULE_ID]
                    )
                ),
                "reasons": list(dict.fromkeys(reasons)),
                "missing_requirements": list(dict.fromkeys(missing)),
                "requires_manual_review": True,
            }
        )
        return reviews

    def _apply_filing_cross_checks(
        self,
        reviews: list[MaterialReview],
        materials: list[Material],
        ocr_fields: list[OcrField],
        project: ProjectInfo,
    ) -> list[MaterialReview]:
        material_categories = {item.material_id: item.category for item in materials}
        filing_fields = [
            item
            for item in ocr_fields
            if item.field_name
            in {
                "project_name",
                "project_entity",
                "insured_name",
                "insured_address",
                "site_address",
                "project_type",
                "component_model",
            }
        ]
        usable = [
            item
            for item in filing_fields
            if item.value_status is OcrValueStatus.EXTRACTED
            and item.confidence >= OCR_MIN_CONFIDENCE
        ]
        updates: dict[str, list[object]] = {}
        for field in usable:
            text = field.normalized_value or field.raw_value or ""
            if field.field_name in {
                "project_name",
                "project_entity",
                "project_type",
                "site_address",
            }:
                matched = [term for term in PROHIBITED_PROJECT_TERMS if term in text]
                if matched:
                    self._add_review_update(
                        updates,
                        field.material_id,
                        MaterialReviewAction.RECOMMEND_REJECT,
                        self.FILING_PROHIBITED_RULE_ID,
                        f"备案信息命中禁投关键词：{'、'.join(matched)}；证据：{text}",
                        field.field_id,
                    )

        expected_fields = {
            "project_name": project.project_name,
            "project_entity": project.project_entity,
            "insured_name": project.insured_name,
            "insured_address": project.insured_address,
            "site_address": project.site_address,
            "component_model": project.component_model,
        }
        actual_by_name = {
            name: [item for item in usable if item.field_name == name]
            for name in expected_fields
        }
        for name, expected in expected_fields.items():
            actual = actual_by_name[name]
            if expected and actual and not any(
                _normalized_text(expected) == _normalized_text(item.normalized_value or item.raw_value)
                for item in actual
            ):
                for item in actual:
                    self._add_review_update(
                        updates,
                        item.material_id,
                        MaterialReviewAction.WARNING,
                        self.CROSS_CHECK_RULE_ID,
                        f"备案证{self._field_label(name)}与投保信息不一致，请核对",
                        item.field_id,
                    )

        official_document_ids = {
            material_id
            for material_id, category in material_categories.items()
            if category
            in {
                MaterialCategory.PROJECT_DOCUMENT,
                MaterialCategory.FILING_CERTIFICATE,
                MaterialCategory.GRID_CONNECTION_DOCUMENT,
            }
        }

        # The challenge explicitly asks for the project entity/insured and
        # project/insured-address consistency checks. Compare OCR evidence from
        # the same official document when both fields are present.
        related_field_pairs = (
            ("project_entity", "insured_name", "项目单位与被保险人信息不一致"),
            ("site_address", "insured_address", "项目地址与被保险地址不一致"),
        )
        for material_id in official_document_ids:
            fields_by_name = {
                name: [
                    item
                    for item in usable
                    if item.material_id == material_id and item.field_name == name
                ]
                for pair in related_field_pairs
                for name in pair[:2]
            }
            for left_name, right_name, reason in related_field_pairs:
                left_fields = fields_by_name[left_name]
                right_fields = fields_by_name[right_name]
                left_values = {
                    _normalized_text(item.normalized_value or item.raw_value)
                    for item in left_fields
                    if item.normalized_value or item.raw_value
                }
                right_values = {
                    _normalized_text(item.normalized_value or item.raw_value)
                    for item in right_fields
                    if item.normalized_value or item.raw_value
                }
                if left_values and right_values and left_values.isdisjoint(right_values):
                    for item in [*left_fields, *right_fields]:
                        self._add_review_update(
                            updates,
                            item.material_id,
                            MaterialReviewAction.WARNING,
                            self.CROSS_CHECK_RULE_ID,
                            f"{reason}，需核验原件及主体关系",
                            item.field_id,
                        )

        cross_document_fields = {
            "project_name",
            "project_entity",
            "insured_name",
            "site_address",
            "insured_address",
        }
        for name in cross_document_fields:
            values = [
                item
                for item in usable
                if item.field_name == name
                and item.material_id in official_document_ids
                and (item.normalized_value or item.raw_value)
            ]
            distinct_values = {
                _normalized_text(item.normalized_value or item.raw_value)
                for item in values
            }
            if len(distinct_values) > 1:
                for item in values:
                    self._add_review_update(
                        updates,
                        item.material_id,
                        MaterialReviewAction.WARNING,
                        self.CROSS_CHECK_RULE_ID,
                        f"備案證與並網材料中的{self._field_label(name)}不一致，需人工核對",
                        item.field_id,
                    )

        expected_component_model = project.component_model
        for item in actual_by_name.get("component_model", []):
            observed = item.normalized_value or item.raw_value
            if (
                expected_component_model
                and observed
                and _normalized_text(expected_component_model) != _normalized_text(observed)
            ):
                self._add_review_update(
                    updates,
                    item.material_id,
                    MaterialReviewAction.WARNING,
                    self.CROSS_CHECK_RULE_ID,
                    "组件铭牌型号与案件录入型号不一致，需核对实物型号和组件目录匹配结果",
                    item.field_id,
                )

        return [self._merge_update(review, updates[review.material_id]) if review.material_id in updates else review for review in reviews]

    @staticmethod
    def _add_review_update(
        updates: dict[str, list[object]],
        material_id: str,
        action: MaterialReviewAction,
        rule_id: str,
        reason: str,
        field_id: str,
    ) -> None:
        values = updates.setdefault(material_id, [[], [], [], [], []])
        values[0].append(action)
        values[1].append(rule_id)
        values[2].append(reason)
        values[3].append(field_id)

    def _merge_update(self, review: MaterialReview, values: list[object]) -> MaterialReview:
        actions, rule_ids, reasons, field_ids, _ = values
        all_actions = [review.action, *actions]
        return review.model_copy(
            update={
                "action": max(all_actions, key=self._ACTION_PRIORITY.__getitem__),
                "triggered_rule_ids": list(dict.fromkeys([*review.triggered_rule_ids, *rule_ids])),
                "reasons": list(dict.fromkeys([*review.reasons, *reasons])),
                "ocr_field_ids": list(dict.fromkeys([*review.ocr_field_ids, *field_ids])),
                "requires_manual_review": review.requires_manual_review or any(
                    action is MaterialReviewAction.WARNING for action in actions
                ),
            }
        )

    @staticmethod
    def _installation_matches(label: str, project: ProjectInfo) -> bool:
        expected = {
            "color_steel_roof": ("彩钢", "钢瓦"),
            "flat_roof": ("平屋顶", "平屋面"),
            "tile_roof": ("瓦屋顶", "瓦片屋顶"),
            "carport_roof": ("车棚", "车棚顶"),
        }.get(project.installation_type.value, ())
        return any(value in label for value in expected)

    @staticmethod
    def _quality_reason(status: MaterialQualityStatus) -> str:
        return {
            MaterialQualityStatus.POOR: "材料质量较差，无法保证自动识别结果可靠",
            MaterialQualityStatus.UNUSABLE: "材料质量不可用，无法进行可靠识别",
            MaterialQualityStatus.UNKNOWN: "材料质量状态未知，无法确认是否满足识别要求",
            MaterialQualityStatus.USABLE: "材料质量满足自动处理要求",
        }[status]

    @staticmethod
    def _require_ocr_fields(
        ocr_fields: list[OcrField],
        required: tuple[str, ...],
        rule_ids: list[str],
        reasons: list[str],
        missing: list[str],
        actions: list[MaterialReviewAction],
    ) -> None:
        reliable_names = {
            item.field_name
            for item in ocr_fields
            if item.value_status is OcrValueStatus.EXTRACTED
            and item.confidence >= OCR_MIN_CONFIDENCE
            and (item.normalized_value or item.raw_value)
        }
        absent = [name for name in required if name not in reliable_names]
        if absent:
            rule_ids.append("DOC-REQUIRED-FIELDS-001")
            actions.append(MaterialReviewAction.REQUEST_MORE)
            reasons.append("材料中的关键字段缺失或 OCR 置信度不足")
            missing.append(
                f"补充可清晰识别的字段：{', '.join(absent)}"
            )

    @staticmethod
    def _field_label(name: str) -> str:
        return {
            "project_name": "项目名称",
            "project_entity": "项目单位",
            "insured_name": "被保险人",
            "insured_address": "被保险地址",
            "component_model": "组件型号",
            "site_address": "项目地址",
        }.get(name, name)

    @staticmethod
    def _material_category_label(category: str) -> str:
        return {
            "panorama": "电站全景照",
            "roof_connection": "屋顶连接处照片",
            "parapet": "女儿墙及排水照片",
            "workshop": "车间内部照片",
            "filing_certificate": "电站备案证",
            "grid_connection_document": "并网许可或调度协议",
            "electrical_grounding": "电气系统与防雷接地照片/记录",
            "component_nameplate": "组件铭牌",
            "inverter_nameplate": "逆变器铭牌",
            "combiner_box": "汇流箱照片",
        }.get(category, category)
