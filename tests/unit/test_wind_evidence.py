"""Synthetic engineering evidence tests; these do not certify a real PV site."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.catastrophe import CatastropheAssessmentEngine
from app.catastrophe.wind import assess_wind_evidence
from app.contracts import (
    AnnualWindPressure,
    ComponentProfile,
    ExpectedLossRisk,
    ParameterApplicabilityStatus,
    WindEngineeringEvidence,
    UnderwritingCase,
)
from app.api.schemas import RealAnalyzeManifest
from app.reports import generate_markdown_report


NOW = datetime(2026, 10, 11, tzinfo=UTC)


def annual(year: int, maximum: float | None, valid_days: int) -> AnnualWindPressure:
    return AnnualWindPressure(
        year=year,
        maximum_pa=maximum,
        valid_days=valid_days,
        expected_days=366 if year == 2024 else 365,
        source_url="https://example.org/verified-annual-series",
        dataset="synthetic-engineering-pressure",
        grid_reference="synthetic-site-point",
    )


def evidence(**changes) -> WindEngineeringEvidence:
    payload = dict(
        component_model="PV-TEST-1000",
        manufacturer="Example PV",
        manual_url="https://example.org/module-installation-manual.pdf",
        manual_version="v1",
        manual_page="p. 8",
        capacity_pa=1000,
        capacity_definition="approved roof installation wind pressure",
        required_mounting="four clamped points at approved zones",
        observed_mounting="four clamped points at approved zones",
        mounting_match=True,
        mounting_material_ids=["roof-connection"],
        installation_reviewer="synthetic reviewer",
        installation_reviewed_at=NOW,
        project_location_confirmed=True,
        location_evidence="cross checked project and image coordinates",
        comparison_basis="approved roof installation wind pressure",
        comparison_method_reference="synthetic engineering method v1",
        comparison_reviewer="synthetic engineer",
        comparison_reviewed_at=NOW,
        annual_pressures=[
            annual(2022, 800, 365),
            annual(2023, 1200, 365),
            annual(2024, 1000, 366),
            annual(2025, 9999, 300),
        ],
    )
    payload.update(changes)
    return WindEngineeringEvidence.model_validate(payload)


def component() -> ComponentProfile:
    return ComponentProfile(
        component_model="PV-TEST-1000",
        manufacturer="Example PV",
        wind_load_pa=1000,
        source_url=None,
        source_name="synthetic component record",
        retrieved_at=NOW,
        match_confidence=1,
    )


def test_complete_wind_evidence_recomputes_r_and_f_without_counting_missing_year():
    status, result = assess_wind_evidence(
        evidence(), component=component(), project_model="PV-TEST-1000"
    )
    assert status is ParameterApplicabilityStatus.USABLE
    assert result.status == "calculated"
    assert result.r_historical_over_capacity == pytest.approx(1.2)
    assert result.f_exceedance_percent == pytest.approx(100 / 3)
    assert result.valid_year_count == 3
    assert result.excluded_year_count == 1
    assert result.technical_result == "historical_exceedance"
    assert result.annual_results[-1].included is False


def test_boundary_equal_capacity_is_not_an_exceedance():
    record = evidence(annual_pressures=[annual(2024, 1000, 366)])
    _, result = assess_wind_evidence(record, component=component())
    assert result.r_historical_over_capacity == 1
    assert result.f_exceedance_percent == 0
    assert result.technical_result == "within_historical_sample"


def test_mismatched_installation_or_model_blocks_numeric_verdict():
    for record in (
        evidence(mounting_match=False),
        evidence(component_model="DIFFERENT-MODEL"),
        evidence(capacity_pa=1200),
    ):
        status, result = assess_wind_evidence(
            record, component=component(), project_model="PV-TEST-1000"
        )
        assert status is ParameterApplicabilityStatus.NOT_APPLICABLE
        assert result.status == "incompatible"
        assert result.r_historical_over_capacity is None
        assert result.f_exceedance_percent is None
        assert result.missing_requirements


def test_missing_approval_or_valid_year_reports_gap_without_division_by_zero():
    status, result = assess_wind_evidence(
        evidence(
            mounting_match=None,
            comparison_method_reference=None,
            annual_pressures=[annual(2025, None, 0)],
        ),
        component=component(),
    )
    assert status is ParameterApplicabilityStatus.PENDING_CONFIRMATION
    assert result.status == "incomplete"
    assert result.f_exceedance_percent is None
    assert result.valid_year_count == 0
    assert any("完整" in item for item in result.missing_requirements)


def test_invalid_year_and_duplicate_year_are_rejected():
    with pytest.raises(ValidationError):
        AnnualWindPressure.model_validate(dict(
            year=2024, maximum_pa=200, valid_days=365, expected_days=365,
            source_url="https://example.org/a", dataset="x", grid_reference="x",
        ))
    with pytest.raises(ValidationError):
        evidence(annual_pressures=[annual(2024, 200, 366), annual(2024, 300, 366)])


def test_case_assessment_records_calculation_but_not_unapproved_insurance_grade():
    result = CatastropheAssessmentEngine().assess(
        component=component(),
        weather=None,
        wind_evidence=evidence(),
        project_model="PV-TEST-1000",
    )
    assert result.wind_comparison.status == "calculated"
    assert result.installation_parameter_reviews[0].status is ParameterApplicabilityStatus.USABLE
    assert "CAT-WIND-HISTORICAL-COMPARISON-CALCULATED" in result.triggered_rule_ids
    assert result.expected_loss_risk is ExpectedLossRisk.UNKNOWN
    assert result.requires_manual_review is True


def test_manifest_rejects_nonexistent_installation_material_reference():
    payload = {
        "case_id": "synthetic-wind-001",
        "project": {
            "project_name": "synthetic test", "insured_name": "synthetic company",
            "project_type": "rooftop", "installation_type": "color_steel_roof",
            "site_address": "synthetic address", "longitude": 113.0, "latitude": 23.0,
            "proposed_start_date": None, "component_model": "PV-TEST-1000",
        },
        "materials": [{"material_id": "other-photo", "category": "roof_connection"}],
        "wind_evidence": evidence().model_dump(mode="json"),
    }
    with pytest.raises(ValidationError, match="unknown materials"):
        RealAnalyzeManifest.model_validate(payload)
    payload["materials"][0]["material_id"] = "roof-connection"
    assert RealAnalyzeManifest.model_validate(payload).wind_evidence is not None


def test_report_shows_annual_sources_exclusions_and_unknown_business_grade():
    record = evidence()
    assessment = CatastropheAssessmentEngine().assess(
        component=component(), weather=None,
        wind_evidence=record, project_model="PV-TEST-1000",
    )
    case = UnderwritingCase.model_validate({
        "schema_version": "0.1.0", "case_id": "synthetic-wind-report",
        "project": {
            "project_name": "synthetic test", "insured_name": "synthetic company",
            "project_type": "rooftop", "installation_type": "color_steel_roof",
            "site_address": "synthetic address", "longitude": 113.0, "latitude": 23.0,
            "proposed_start_date": None, "component_model": "PV-TEST-1000",
        },
        "materials": [{
            "material_id": "roof-connection", "category": "roof_connection",
            "file_name": "synthetic.jpg", "media_type": "image/jpeg",
            "quality_status": "usable", "quality_issues": [], "parse_status": "success",
        }],
        "ocr_fields": [], "findings": [], "material_reviews": [],
        "processing_trace": [],
        "wind_evidence": record.model_dump(mode="json"),
        "component_profile": component().model_dump(mode="json"),
        "catastrophe_assessment": assessment.model_dump(mode="json"),
    })
    report = generate_markdown_report(case)
    assert "风灾工程证据与年度复算" in report
    assert "2025" in report and "已排除" in report
    assert "https://example.org/verified-annual-series" in report
    assert "R = 完整年度历史最大工程风压" in report
    assert "不能据此自动承保或拒保" in report
