from app.contracts import (
    CaptureView,
    DecisionType,
    DetectionStatus,
    EnvironmentRelation,
    Material,
    MaterialCategory,
    MaterialParseStatus,
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
    RiskSeverity,
    UnderwritingCase,
    WatermarkStatus,
)
from app.decision import DecisionEngine
from app.rules import RuleEngine
from app.rules.engine import EXPECTED_CHECKS_BY_MATERIAL


def make_material(
    material_id: str,
    category: MaterialCategory,
    *,
    view: CaptureView = CaptureView.UNKNOWN,
) -> Material:
    return Material(
        material_id=material_id,
        category=category,
        capture_view=view,
        file_name=f"{material_id}.jpg",
        media_type="image/jpeg",
        quality_status=MaterialQualityStatus.USABLE,
        quality_issues=[],
        parse_status=MaterialParseStatus.SUCCESS,
    )


def make_project(**updates: object) -> ProjectInfo:
    payload: dict[str, object] = {
        "project_name": "样例屋顶项目",
        "insured_name": "样例企业",
        "project_type": "rooftop",
        "installation_type": "color_steel_roof",
        "site_address": "广东省广州市天河区",
        "longitude": 113.3,
        "latitude": 23.1,
        "proposed_start_date": "2026-10-01",
        "component_model": "PV-580W-X",
    }
    payload.update(updates)
    return ProjectInfo(**payload)


def make_finding(
    material_id: str,
    category: RiskCategory,
    status: DetectionStatus,
    *,
    environment_relation: EnvironmentRelation | None = None,
    confidence: float = 0.95,
    requires_manual_review: bool = False,
) -> RiskFinding:
    if environment_relation is None:
        environment_relation = (
            EnvironmentRelation.PROJECT_SITE
            if category in EXPECTED_CHECKS_BY_MATERIAL[MaterialCategory.PANORAMA]
            and category.value.endswith("_environment")
            and status is DetectionStatus.DETECTED
            else EnvironmentRelation.UNCERTAIN
        )
    return RiskFinding(
        finding_id=f"{material_id}:{category.value}",
        material_id=material_id,
        category=category,
        label=category.value,
        detection_status=status,
        severity=RiskSeverity.HIGH,
        confidence=confidence,
        environment_relation=environment_relation,
        bbox=None,
        evidence_text="测试证据",
        provider="test-vision",
        model="test-model",
        requires_manual_review=requires_manual_review,
    )


def test_package_gate_checks_photo_count_certificate_and_both_views() -> None:
    materials = [
        make_material("front", MaterialCategory.PANORAMA, view=CaptureView.FRONT_LEVEL),
        make_material("top", MaterialCategory.PANORAMA, view=CaptureView.OVERHEAD),
        make_material("roof", MaterialCategory.ROOF_CONNECTION),
        make_material("workshop", MaterialCategory.WORKSHOP),
        Material(
            material_id="certificate",
            category=MaterialCategory.FILING_CERTIFICATE,
            file_name="certificate.pdf",
            media_type="application/pdf",
            quality_status=MaterialQualityStatus.USABLE,
            quality_issues=[],
            parse_status=MaterialParseStatus.SUCCESS,
        ),
    ]

    assessment = RuleEngine().assess_package(materials)

    assert assessment.image_count == 4
    assert assessment.panorama_count == 2
    assert assessment.has_filing_certificate is True
    assert assessment.has_front_level_panorama is True
    assert assessment.has_overhead_panorama is True
    assert assessment.missing_material_categories == [
        "parapet",
        "grid_connection_document",
        "electrical_grounding",
        "component_nameplate",
        "inverter_nameplate",
        "combiner_box",
    ]
    assert "至少提交5张图片材料（当前4张）" in assessment.missing_requirements
    assert any("并网许可或调度协议" in item for item in assessment.missing_requirements)


def test_carport_package_does_not_require_rooftop_workshop_material() -> None:
    assessment = RuleEngine().assess_package([], project_type=ProjectType.CARPORT)

    assert "workshop" not in assessment.missing_material_categories


def test_workshop_industry_without_official_list_is_never_auto_cleared() -> None:
    material = make_material("workshop", MaterialCategory.WORKSHOP)
    engine = RuleEngine()
    findings = [
        make_finding(material.material_id, category, DetectionStatus.NOT_DETECTED)
        for category in (
            engine._expected_checks_for_material(MaterialCategory.WORKSHOP) or frozenset()
        )
    ]

    missing_industry = engine.evaluate_materials(
        [material], findings=findings, project=make_project()
    )[0]
    provided_industry = engine.evaluate_materials(
        [material], findings=findings, project=make_project(industry_name="电子制造")
    )[0]

    assert missing_industry.action is MaterialReviewAction.REQUEST_MORE
    assert missing_industry.requires_manual_review is True
    assert any("所属行业" in item for item in missing_industry.missing_requirements)
    assert provided_industry.action is MaterialReviewAction.WARNING
    assert provided_industry.requires_manual_review is True
    assert any("正式高火险行业清单尚未配置" in item for item in provided_industry.reasons)


def test_pdf_tagged_as_panorama_cannot_satisfy_photo_or_view_gates() -> None:
    materials = [
        Material(
            material_id="panorama-pdf",
            category=MaterialCategory.PANORAMA,
            capture_view=CaptureView.FRONT_LEVEL,
            file_name="panorama.pdf",
            media_type="application/pdf",
            quality_status=MaterialQualityStatus.USABLE,
            quality_issues=[],
            parse_status=MaterialParseStatus.SUCCESS,
        )
    ]

    assessment = RuleEngine().assess_package(materials)

    assert assessment.image_count == 0
    assert assessment.panorama_count == 0
    assert assessment.has_front_level_panorama is False
    assert assessment.has_overhead_panorama is False


def test_explicit_excluded_environment_recommends_rejection() -> None:
    material = make_material("panorama", MaterialCategory.PANORAMA)
    findings = [
        make_finding(material.material_id, category, DetectionStatus.NOT_DETECTED)
        for category in EXPECTED_CHECKS_BY_MATERIAL[MaterialCategory.PANORAMA]
    ]
    findings.append(
        make_finding(
            material.material_id,
            RiskCategory.AGRICULTURE_ENVIRONMENT,
            DetectionStatus.DETECTED,
        )
    )

    review = RuleEngine().evaluate_material(
        material,
        findings=findings,
        project=make_project(),
    )

    assert review.action is MaterialReviewAction.RECOMMEND_REJECT
    assert "ENV-EXCLUDED-001" in review.triggered_rule_ids


def test_uncovered_environment_check_requests_more_material() -> None:
    material = make_material("panorama", MaterialCategory.PANORAMA)
    findings = [
        make_finding(
            material.material_id,
            RiskCategory.AGRICULTURE_ENVIRONMENT,
            DetectionStatus.NOT_DETECTED,
        )
    ]

    review = RuleEngine().evaluate_materials([material], findings=findings)[0]

    assert review.action is MaterialReviewAction.REQUEST_MORE
    assert "ENV-COVERAGE-001" in review.triggered_rule_ids


def test_missing_panorama_watermark_is_a_non_blocking_suggestion() -> None:
    material = make_material("panorama", MaterialCategory.PANORAMA)
    findings = [
        make_finding(material.material_id, category, DetectionStatus.NOT_DETECTED)
        for category in EXPECTED_CHECKS_BY_MATERIAL[MaterialCategory.PANORAMA]
    ]
    review = RuleEngine().evaluate_material(material, findings=findings)

    assert review.action is MaterialReviewAction.WARNING
    assert "IMG-WATERMARK-001" in review.triggered_rule_ids
    assert review.missing_requirements == []


def test_complementary_panorama_views_share_environment_and_risk_coverage() -> None:
    first = make_material("front", MaterialCategory.PANORAMA, view=CaptureView.FRONT_LEVEL)
    second = make_material("overhead", MaterialCategory.PANORAMA, view=CaptureView.OVERHEAD)
    expected = EXPECTED_CHECKS_BY_MATERIAL[MaterialCategory.PANORAMA]
    first_findings = [
        make_finding(first.material_id, category, DetectionStatus.NOT_DETECTED)
        for category in expected
        if category is not RiskCategory.FOREST_ENVIRONMENT
    ]
    second_findings = [
        make_finding(second.material_id, category, DetectionStatus.NOT_DETECTED)
        for category in expected
        if category is not RiskCategory.AGRICULTURE_ENVIRONMENT
    ]

    reviews = RuleEngine().evaluate_materials(
        [first, second], findings=[*first_findings, *second_findings]
    )

    assert all(review.action is MaterialReviewAction.WARNING for review in reviews)
    assert all("ENV-COVERAGE-001" not in review.triggered_rule_ids for review in reviews)
    assert all(not review.missing_requirements for review in reviews)


def test_environment_visible_only_in_distant_background_does_not_reject() -> None:
    material = make_material("panorama", MaterialCategory.PANORAMA)
    environment_categories = {
        category
        for category in EXPECTED_CHECKS_BY_MATERIAL[MaterialCategory.PANORAMA]
        if category.value.endswith("_environment")
    }
    findings = [
        make_finding(material.material_id, category, DetectionStatus.NOT_DETECTED)
        for category in EXPECTED_CHECKS_BY_MATERIAL[MaterialCategory.PANORAMA]
        if category not in environment_categories
    ]
    findings.extend(
        make_finding(
            material.material_id,
            category,
            DetectionStatus.DETECTED,
            environment_relation=EnvironmentRelation.DISTANT_BACKGROUND,
        )
        for category in sorted(environment_categories, key=lambda item: item.value)
    )

    review = RuleEngine().evaluate_material(material, findings=findings)

    assert review.action is MaterialReviewAction.WARNING
    assert "ENV-EXCLUDED-001" not in review.triggered_rule_ids
    assert "ENV-BACKGROUND-CONTEXT-001" in review.triggered_rule_ids
    assert review.requires_manual_review is False


def test_nearby_environment_routes_to_manual_review_until_boundary_is_defined() -> None:
    material = make_material("panorama", MaterialCategory.PANORAMA)
    findings = [
        make_finding(material.material_id, category, DetectionStatus.NOT_DETECTED)
        for category in EXPECTED_CHECKS_BY_MATERIAL[MaterialCategory.PANORAMA]
    ]
    findings.append(
        make_finding(
            material.material_id,
            RiskCategory.AGRICULTURE_ENVIRONMENT,
            DetectionStatus.DETECTED,
            environment_relation=EnvironmentRelation.OPERATIONAL_SURROUNDINGS,
        )
    )

    review = RuleEngine().evaluate_material(material, findings=findings)

    assert review.action is MaterialReviewAction.WARNING
    assert review.requires_manual_review is True
    assert "ENV-EXCLUDED-001" not in review.triggered_rule_ids
    assert "ENV-SITE-RELATION-REVIEW-001" in review.triggered_rule_ids
    assert any("边界尚待业务确认" in reason for reason in review.reasons)


def test_uncertain_site_relation_routes_to_manual_review_without_auto_rejection() -> None:
    material = make_material("panorama", MaterialCategory.PANORAMA)
    findings = [
        make_finding(material.material_id, category, DetectionStatus.NOT_DETECTED)
        for category in EXPECTED_CHECKS_BY_MATERIAL[MaterialCategory.PANORAMA]
    ]
    findings.append(
        make_finding(
            material.material_id,
            RiskCategory.AGRICULTURE_ENVIRONMENT,
            DetectionStatus.DETECTED,
            environment_relation=EnvironmentRelation.UNCERTAIN,
        )
    )

    review = RuleEngine().evaluate_material(material, findings=findings)

    assert review.action is MaterialReviewAction.WARNING
    assert review.requires_manual_review is True
    assert "ENV-EXCLUDED-001" not in review.triggered_rule_ids
    assert "ENV-SITE-RELATION-REVIEW-001" in review.triggered_rule_ids
    assert review.missing_requirements == []


def test_model_manual_review_flag_suppresses_environment_auto_rejection() -> None:
    material = make_material("panorama", MaterialCategory.PANORAMA)
    findings = [
        make_finding(material.material_id, category, DetectionStatus.NOT_DETECTED)
        for category in EXPECTED_CHECKS_BY_MATERIAL[MaterialCategory.PANORAMA]
    ]
    findings.append(
        make_finding(
            material.material_id,
            RiskCategory.AGRICULTURE_ENVIRONMENT,
            DetectionStatus.DETECTED,
            environment_relation=EnvironmentRelation.PROJECT_SITE,
            requires_manual_review=True,
        )
    )

    review = RuleEngine().evaluate_material(material, findings=findings)

    assert review.action is MaterialReviewAction.WARNING
    assert review.requires_manual_review is True
    assert "ENV-EXCLUDED-001" not in review.triggered_rule_ids


def test_low_confidence_site_environment_is_not_an_automatic_rejection() -> None:
    material = make_material("panorama", MaterialCategory.PANORAMA)
    findings = [
        make_finding(material.material_id, category, DetectionStatus.NOT_DETECTED)
        for category in EXPECTED_CHECKS_BY_MATERIAL[MaterialCategory.PANORAMA]
    ]
    findings.append(
        make_finding(
            material.material_id,
            RiskCategory.AGRICULTURE_ENVIRONMENT,
            DetectionStatus.DETECTED,
            environment_relation=EnvironmentRelation.PROJECT_SITE,
            confidence=0.64,
        )
    )

    review = RuleEngine().evaluate_material(material, findings=findings)

    assert review.action is MaterialReviewAction.WARNING
    assert review.requires_manual_review is True
    assert "ENV-EXCLUDED-001" not in review.triggered_rule_ids
    assert any("0.64" in reason and "0.65" in reason for reason in review.reasons)


def test_legacy_finding_without_environment_relation_is_not_auto_rejected() -> None:
    material = make_material("panorama", MaterialCategory.PANORAMA)
    finding_payload = make_finding(
        material.material_id,
        RiskCategory.FOREST_ENVIRONMENT,
        DetectionStatus.DETECTED,
    ).model_dump(mode="python")
    finding_payload.pop("environment_relation")
    legacy_finding = RiskFinding.model_validate(finding_payload)
    findings = [
        make_finding(material.material_id, category, DetectionStatus.NOT_DETECTED)
        for category in EXPECTED_CHECKS_BY_MATERIAL[MaterialCategory.PANORAMA]
    ]
    findings.append(legacy_finding)

    review = RuleEngine().evaluate_material(material, findings=findings)

    assert legacy_finding.environment_relation is EnvironmentRelation.UNCERTAIN
    assert review.action is MaterialReviewAction.WARNING
    assert review.requires_manual_review is True
    assert "ENV-EXCLUDED-001" not in review.triggered_rule_ids


def test_watermarked_panorama_outside_fifteen_day_window_requests_more() -> None:
    material_data = make_material("panorama", MaterialCategory.PANORAMA).model_dump(
        mode="python"
    )
    material_data.update(
        {
            "watermark_status": WatermarkStatus.PRESENT,
            "captured_at": "2026-09-10T10:00:00+08:00",
            "longitude": 113.3,
            "latitude": 23.1,
        }
    )
    material = Material.model_validate(material_data)

    review = RuleEngine().evaluate_material(material, project=make_project())

    assert review.action is MaterialReviewAction.REQUEST_MORE
    assert "IMG-WATERMARK-DATE-001" in review.triggered_rule_ids
    assert "补拍拟起保日前15日内的全景照片" in review.missing_requirements


def test_grounding_record_requires_test_fields_and_visual_coverage() -> None:
    material = make_material("grounding", MaterialCategory.ELECTRICAL_GROUNDING)

    review = RuleEngine().evaluate_material(material)

    assert review.action is MaterialReviewAction.REQUEST_MORE
    assert "ENV-COVERAGE-001" in review.triggered_rule_ids
    assert "DOC-REQUIRED-FIELDS-001" in review.triggered_rule_ids


def test_poor_image_quality_requests_replacement_even_when_other_checks_are_clear() -> None:
    material = make_material("panorama", MaterialCategory.PANORAMA)
    findings = [
        make_finding(material.material_id, category, DetectionStatus.NOT_DETECTED)
        for category in EXPECTED_CHECKS_BY_MATERIAL[MaterialCategory.PANORAMA]
        if category is not RiskCategory.IMAGE_QUALITY
    ]
    findings.append(
        make_finding(material.material_id, RiskCategory.IMAGE_QUALITY, DetectionStatus.DETECTED)
    )

    review = RuleEngine().evaluate_material(material, findings=findings)

    assert review.action is MaterialReviewAction.REQUEST_MORE
    assert "MAT-QUALITY-001" in review.triggered_rule_ids
    assert any("补拍" in item for item in review.missing_requirements)


def test_monitoring_material_is_flagged_for_discount_review_without_rate_guess() -> None:
    material = make_material("monitoring", MaterialCategory.MONITORING_OPTIONAL)
    field = OcrField(
        field_id="monitoring:present",
        material_id="monitoring",
        field_name="monitoring_present",
        raw_value="有",
        normalized_value="true",
        value_status=OcrValueStatus.EXTRACTED,
        confidence=0.95,
        provider="test-ocr",
        model="test-model",
    )

    review = RuleEngine().evaluate_material(
        material,
        findings=[
            make_finding(
                material.material_id,
                RiskCategory.IMAGE_QUALITY,
                DetectionStatus.NOT_DETECTED,
            ),
            make_finding(
                material.material_id,
                RiskCategory.MONITORING_EFFECTIVE_COVERAGE,
                DetectionStatus.DETECTED,
            ),
        ],
        ocr_fields=[field],
    )

    assert review.action is MaterialReviewAction.WARNING
    assert review.requires_manual_review is True
    assert "DISC-MONITORING-REVIEW-001" in review.triggered_rule_ids
    assert any("不推定折扣" in reason for reason in review.reasons)


def test_filing_prohibited_keyword_recommends_rejection() -> None:
    material = Material(
        material_id="certificate",
        category=MaterialCategory.FILING_CERTIFICATE,
        file_name="certificate.pdf",
        media_type="application/pdf",
        quality_status=MaterialQualityStatus.USABLE,
        quality_issues=[],
        parse_status=MaterialParseStatus.SUCCESS,
    )
    fields = [
        OcrField(
            field_id=f"certificate:{name}",
            material_id="certificate",
            field_name=name,
            raw_value=value,
            normalized_value=value,
            value_status=OcrValueStatus.EXTRACTED,
            confidence=0.95,
            provider="test-ocr",
            model="test-model",
        )
        for name, value in (
            ("project_name", "某某渔光项目"),
            ("site_address", "广东省广州市天河区"),
            ("insured_name", "样例企业"),
        )
    ]

    review = RuleEngine().evaluate_materials(
        [material],
        ocr_fields=fields,
        project=make_project(),
    )[0]

    assert review.action is MaterialReviewAction.RECOMMEND_REJECT
    assert "DOC-FILING-EXCLUDED-001" in review.triggered_rule_ids


def test_filing_and_grid_documents_are_cross_checked() -> None:
    materials = [
        Material(
            material_id="filing",
            category=MaterialCategory.FILING_CERTIFICATE,
            file_name="filing.pdf",
            media_type="application/pdf",
            quality_status=MaterialQualityStatus.USABLE,
            quality_issues=[],
            parse_status=MaterialParseStatus.SUCCESS,
        ),
        Material(
            material_id="grid",
            category=MaterialCategory.GRID_CONNECTION_DOCUMENT,
            file_name="grid.pdf",
            media_type="application/pdf",
            quality_status=MaterialQualityStatus.USABLE,
            quality_issues=[],
            parse_status=MaterialParseStatus.SUCCESS,
        ),
    ]
    fields = []
    values = {
        "filing": {
            "project_name": "光伏项目甲",
            "project_entity": "示例企业",
            "site_address": "广东省广州市天河区",
            "insured_name": "示例企业",
        },
        "grid": {
            "project_name": "光伏项目乙",
            "project_entity": "示例企业",
            "site_address": "广东省广州市天河区",
            "grid_connection_date": "2026-01-01",
        },
    }
    for material_id, material_fields in values.items():
        for field_name, value in material_fields.items():
            fields.append(
                OcrField(
                    field_id=f"{material_id}:{field_name}",
                    material_id=material_id,
                    field_name=field_name,
                    raw_value=value,
                    normalized_value=value,
                    value_status=OcrValueStatus.EXTRACTED,
                    confidence=0.95,
                    provider="test-ocr",
                    model="test-model",
                )
            )

    reviews = RuleEngine().evaluate_materials(
        materials,
        ocr_fields=fields,
        project=make_project(project_name="光伏项目甲"),
    )

    assert all("DOC-CROSS-CHECK-001" in review.triggered_rule_ids for review in reviews)
    assert all(review.requires_manual_review for review in reviews)


def test_explicit_rejection_takes_priority_over_missing_package_items() -> None:
    material = make_material("panorama", MaterialCategory.PANORAMA)
    review = MaterialReview(
        material_id=material.material_id,
        action=MaterialReviewAction.RECOMMEND_REJECT,
        triggered_rule_ids=["ENV-EXCLUDED-001"],
        finding_ids=[],
        ocr_field_ids=[],
        reasons=["发现明确拒保环境"],
        missing_requirements=[],
        requires_manual_review=False,
    )
    case = UnderwritingCase(
        schema_version="0.1.0",
        case_id="case-reject-and-missing",
        project=make_project(longitude=None),
        materials=[material],
        ocr_fields=[],
        findings=[],
        material_reviews=[review],
        package_assessment=PackageAssessment(
            image_count=1,
            panorama_count=1,
            has_filing_certificate=False,
            has_front_level_panorama=False,
            has_overhead_panorama=False,
            missing_requirements=["补充备案证"],
        ),
        processing_trace=[],
    )

    decision = DecisionEngine().decide(case)

    assert decision.decision is DecisionType.RECOMMEND_REJECT
    assert "补充备案证" in decision.missing_requirements
    assert "REQ-PROJECT-COORDINATES" in decision.decisive_rule_ids
