from datetime import date
from io import BytesIO

from app.contracts import (
    DetectionStatus,
    Material,
    MaterialCategory,
    MaterialParseStatus,
    MaterialQualityStatus,
    MaterialReviewAction,
    OcrField,
    OcrValueStatus,
    ProjectInfo,
    RiskCategory,
    RiskFinding,
    RiskSeverity,
)
from app.intake.files import assess_image_quality
from app.rules.config import BusinessRulesConfig
from app.rules.engine import EXPECTED_CHECKS_BY_MATERIAL, RuleEngine
from PIL import Image, ImageDraw


def material(category: MaterialCategory, material_id: str = "m1") -> Material:
    return Material(
        material_id=material_id,
        category=category,
        file_name=f"{material_id}.jpg",
        media_type="image/jpeg",
        quality_status=MaterialQualityStatus.USABLE,
        quality_issues=[],
        parse_status=MaterialParseStatus.SUCCESS,
    )


def project(**updates: object) -> ProjectInfo:
    values: dict[str, object] = {
        "project_name": "测试光伏项目",
        "insured_name": "乙能源有限公司",
        "project_entity": "甲能源有限公司",
        "insured_address": "广东省广州市天河区甲路1号",
        "site_address": "广东省广州市天河区乙路2号",
        "project_type": "rooftop",
        "installation_type": "color_steel_roof",
        "longitude": 113.3,
        "latitude": 23.1,
        "proposed_start_date": date(2026, 10, 1),
        "component_model": "PV-580W-X",
    }
    values.update(updates)
    return ProjectInfo(**values)


def finding(
    material_id: str,
    category: RiskCategory,
    status: DetectionStatus,
) -> RiskFinding:
    return RiskFinding(
        finding_id=f"{material_id}:{category.value}:{status.value}",
        material_id=material_id,
        category=category,
        label=category.value,
        detection_status=status,
        severity=RiskSeverity.HIGH,
        confidence=0.95,
        bbox=None,
        evidence_text="可见测试证据",
        provider="test-vision",
        model="test-model",
        requires_manual_review=False,
    )


def negative_findings(engine: RuleEngine, item: Material) -> list[RiskFinding]:
    categories = engine._expected_checks_for_material(item.category)
    return [
        finding(item.material_id, category, DetectionStatus.NOT_DETECTED)
        for category in (categories or EXPECTED_CHECKS_BY_MATERIAL[item.category])
    ]


def ocr_field(material_id: str, name: str, value: str) -> OcrField:
    return OcrField(
        field_id=f"{material_id}:{name}",
        material_id=material_id,
        field_name=name,
        raw_value=value,
        normalized_value=value,
        value_status=OcrValueStatus.EXTRACTED,
        confidence=0.98,
        provider="test-ocr",
        model="test-model",
    )


def image_bytes(*, size: tuple[int, int], dark: bool, detailed: bool) -> bytes:
    image = Image.new("RGB", size, color=(8, 8, 8) if dark else (220, 220, 220))
    if detailed:
        draw = ImageDraw.Draw(image)
        for x in range(0, size[0], 24):
            color = (20, 20, 20) if x % 48 else (245, 245, 245)
            draw.rectangle((x, 0, x + 11, size[1]), fill=color)
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


def test_quality_preflight_marks_dark_small_and_blurry_photos() -> None:
    status, issues, luminance, sharpness = assess_image_quality(
        image_bytes(size=(320, 240), dark=True, detailed=False)
    )

    assert status is MaterialQualityStatus.POOR
    assert {"low_resolution", "underexposed", "suspected_blur_or_insufficient_detail"} <= set(issues)
    assert luminance is not None and luminance < 24.0
    assert sharpness is not None and sharpness < 35.0


def test_quality_preflight_accepts_clear_well_lit_photo() -> None:
    status, issues, luminance, sharpness = assess_image_quality(
        image_bytes(size=(1200, 900), dark=False, detailed=True)
    )

    assert status is MaterialQualityStatus.USABLE
    assert issues == []
    assert luminance is not None and luminance >= 24.0
    assert sharpness is not None and sharpness >= 35.0


def test_quality_preflight_handles_tiny_valid_images() -> None:
    status, issues, luminance, sharpness = assess_image_quality(
        image_bytes(size=(1, 1), dark=False, detailed=False)
    )

    assert status is MaterialQualityStatus.POOR
    assert "low_resolution" in issues
    assert sharpness == 0.0
    assert luminance is not None


def test_ocr_directly_compares_project_entity_and_insured_fields() -> None:
    item = Material(
        material_id="filing",
        category=MaterialCategory.FILING_CERTIFICATE,
        file_name="filing.pdf",
        media_type="application/pdf",
        quality_status=MaterialQualityStatus.USABLE,
        quality_issues=[],
        parse_status=MaterialParseStatus.SUCCESS,
    )
    fields = [
        ocr_field("filing", "project_name", "测试光伏项目"),
        ocr_field("filing", "project_entity", "甲能源有限公司"),
        ocr_field("filing", "insured_name", "乙能源有限公司"),
        ocr_field("filing", "site_address", "广东省广州市天河区乙路2号"),
        ocr_field("filing", "insured_address", "广东省广州市天河区甲路1号"),
    ]

    review = RuleEngine().evaluate_materials(
        [item], ocr_fields=fields, project=project()
    )[0]

    assert review.action is MaterialReviewAction.WARNING
    assert any("项目单位与被保险人" in reason for reason in review.reasons)
    assert any("项目地址与被保险地址" in reason for reason in review.reasons)


def test_unprotected_cable_is_rejected_under_the_midterm_rule() -> None:
    engine = RuleEngine()
    item = material(MaterialCategory.ELECTRICAL_GROUNDING)
    findings = negative_findings(engine, item)
    findings.append(finding(item.material_id, RiskCategory.UNPROTECTED_CABLE, DetectionStatus.DETECTED))

    review = engine.evaluate_material(item, findings=findings)

    assert review.action is MaterialReviewAction.RECOMMEND_REJECT
    assert "ELEC-UNPROTECTED-CABLE-REJECT-001" in review.triggered_rule_ids


def test_irrelevant_detection_does_not_affect_material_decision() -> None:
    engine = RuleEngine()
    item = material(MaterialCategory.ROOF_CONNECTION)
    findings = negative_findings(engine, item)
    irrelevant = finding(
        item.material_id,
        RiskCategory.FLAMMABLE_MATERIAL,
        DetectionStatus.DETECTED,
    )
    findings.append(irrelevant)

    review = engine.evaluate_material(item, findings=findings)

    assert review.action is MaterialReviewAction.PASS
    assert irrelevant.finding_id not in review.finding_ids
    assert "IMG-FINDING-WARNING-001" not in review.triggered_rule_ids


def test_prohibited_environment_still_rejects_when_visible_at_roof_connection() -> None:
    engine = RuleEngine()
    item = material(MaterialCategory.ROOF_CONNECTION)
    findings = negative_findings(engine, item)
    findings.append(
        finding(
            item.material_id,
            RiskCategory.WATER_ADJACENT_ENVIRONMENT,
            DetectionStatus.DETECTED,
        )
    )

    review = engine.evaluate_material(item, findings=findings)

    assert review.action is MaterialReviewAction.RECOMMEND_REJECT
    assert "ENV-EXCLUDED-001" in review.triggered_rule_ids


def test_monitoring_coverage_is_a_discount_candidate_not_an_automatic_discount() -> None:
    engine = RuleEngine()
    item = material(MaterialCategory.MONITORING_OPTIONAL)
    findings = negative_findings(engine, item)
    findings.append(
        finding(
            item.material_id,
            RiskCategory.MONITORING_EFFECTIVE_COVERAGE,
            DetectionStatus.DETECTED,
        )
    )

    review = engine.evaluate_material(item, findings=findings, project=project())

    assert review.action is MaterialReviewAction.WARNING
    assert review.requires_manual_review is True
    assert any("优惠候选" in reason for reason in review.reasons)


def test_configured_high_fire_industry_requires_surcharge_confirmation() -> None:
    config = BusinessRulesConfig(
        ruleset_id="test",
        version="1",
        source_note="test-only official list fixture",
        high_fire_risk_industries=("化工",),
        advanced_checks_enabled=False,
    )
    engine = RuleEngine(config=config)
    item = material(MaterialCategory.WORKSHOP, "workshop")
    findings = negative_findings(engine, item)

    unpaid = engine.evaluate_materials(
        [item], findings=findings, project=project(industry_name="精细化工", fire_surcharge_confirmed=False)
    )[0]
    confirmed = engine.evaluate_materials(
        [item], findings=findings, project=project(industry_name="精细化工", fire_surcharge_confirmed=True)
    )[0]

    assert unpaid.action is MaterialReviewAction.REQUEST_MORE
    assert any("加费依据" in requirement for requirement in unpaid.missing_requirements)
    assert confirmed.action is MaterialReviewAction.WARNING
    assert confirmed.requires_manual_review is True


def test_config_rejects_critical_threshold_above_one() -> None:
    try:
        BusinessRulesConfig(
            ruleset_id="bad",
            version="1",
            source_note="test",
            catastrophe_critical_shortfall_ratio=1.2,
        )
    except ValueError as error:
        assert "less than 1" in str(error)
    else:
        raise AssertionError("a critical shortfall ratio above one was accepted")
