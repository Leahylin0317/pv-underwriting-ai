from datetime import UTC, datetime

from app.contracts import (
    DecisionType,
    Material,
    MaterialParseStatus,
    MaterialQualityStatus,
    MaterialReview,
    MaterialReviewAction,
    ProcessingStatus,
    ProcessingStep,
    ProcessingTrace,
    ProjectInfo,
    UnderwritingCase,
)
from app.decision import DecisionEngine


def project_info(
    *,
    longitude: float | None = 113.25,
    latitude: float | None = 23.12,
    component_model: str | None = "PV-MODULE-580W",
) -> ProjectInfo:
    return ProjectInfo(
        project_name="示例光伏项目",
        insured_name="示例企业",
        project_type="rooftop",
        installation_type="color_steel_roof",
        site_address="广东省示例市",
        longitude=longitude,
        latitude=latitude,
        proposed_start_date="2026-10-01",
        component_model=component_model,
    )


def material() -> Material:
    return Material(
        material_id="material-001",
        category="panorama",
        file_name="example.jpg",
        media_type="image/jpeg",
        quality_status=MaterialQualityStatus.POOR,
        quality_confidence=0.4,
        quality_issues=["blur"],
        parse_status=MaterialParseStatus.SUCCESS,
    )


def processing_trace(status: ProcessingStatus) -> ProcessingTrace:
    timestamp = datetime.now(UTC)
    return ProcessingTrace(
        step=ProcessingStep.OCR,
        provider="test-provider",
        model="test-model",
        started_at=timestamp,
        finished_at=timestamp,
        latency_ms=0,
        status=status,
        error_code=None,
        error_message=None,
    )


def underwriting_case(
    *,
    project: ProjectInfo | None = None,
    materials: list[Material] | None = None,
    reviews: list[MaterialReview] | None = None,
    traces: list[ProcessingTrace] | None = None,
) -> UnderwritingCase:
    return UnderwritingCase(
        schema_version="0.1.0",
        case_id="case-001",
        project=project or project_info(),
        materials=materials or [],
        ocr_fields=[],
        findings=[],
        component_profile=None,
        weather_profile=None,
        catastrophe_assessment=None,
        material_reviews=reviews or [],
        decision=None,
        processing_trace=traces or [],
    )


def test_decision_engine_defaults_to_manual_review() -> None:
    decision = DecisionEngine().decide(underwriting_case())

    assert decision.decision is DecisionType.MANUAL_REVIEW
    assert decision.missing_requirements == []


def test_decision_engine_requests_coordinates() -> None:
    case = underwriting_case(
        project=project_info(longitude=None, latitude=None)
    )

    decision = DecisionEngine().decide(case)

    assert decision.decision is DecisionType.REQUEST_MORE
    assert "补充项目准确经纬度" in decision.missing_requirements
    assert "REQ-PROJECT-COORDINATES" in decision.decisive_rule_ids


def test_decision_engine_requests_component_model() -> None:
    case = underwriting_case(
        project=project_info(component_model=None)
    )

    decision = DecisionEngine().decide(case)

    assert decision.decision is DecisionType.REQUEST_MORE
    assert "补充光伏组件完整型号" in decision.missing_requirements
    assert "REQ-COMPONENT-MODEL" in decision.decisive_rule_ids


def test_decision_engine_uses_material_review() -> None:
    review = MaterialReview(
        material_id="material-001",
        action=MaterialReviewAction.REQUEST_MORE,
        triggered_rule_ids=["MAT-QUALITY-001"],
        finding_ids=[],
        ocr_field_ids=[],
        reasons=["材料质量较差"],
        missing_requirements=["补充清晰材料"],
        requires_manual_review=False,
    )
    case = underwriting_case(
        materials=[material()],
        reviews=[review],
    )

    decision = DecisionEngine().decide(case)

    assert decision.decision is DecisionType.REQUEST_MORE
    assert "MAT-QUALITY-001" in decision.decisive_rule_ids
    assert "补充清晰材料" in decision.missing_requirements


def test_decision_engine_sends_provider_failure_to_manual_review() -> None:
    case = underwriting_case(
        traces=[processing_trace(ProcessingStatus.FAILED)]
    )

    decision = DecisionEngine().decide(case)

    assert decision.decision is DecisionType.MANUAL_REVIEW
    assert "SYS-PROVIDER-FAILURE" in decision.decisive_rule_ids
    assert decision.warnings


def test_request_more_takes_priority_over_provider_failure() -> None:
    case = underwriting_case(
        project=project_info(component_model=None),
        traces=[processing_trace(ProcessingStatus.FAILED)],
    )

    decision = DecisionEngine().decide(case)

    assert decision.decision is DecisionType.REQUEST_MORE
    assert "补充光伏组件完整型号" in decision.missing_requirements
    assert decision.warnings