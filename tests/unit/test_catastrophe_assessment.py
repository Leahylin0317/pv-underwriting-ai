from datetime import UTC, date, datetime

from app.catastrophe import CatastropheAssessmentEngine
from app.contracts import (
    ComponentProfile,
    ExpectedLossRisk,
    ResistanceLevel,
    WeatherProfile,
)


def component(
    *,
    wind_load_pa: float | None = 2400,
    hail_resistance_mm: float | None = 25,
    snow_load_pa: float | None = 5400,
) -> ComponentProfile:
    return ComponentProfile(
        component_model="PV-MODULE-580W",
        manufacturer="示例厂商",
        rated_power_w=580,
        hail_resistance_mm=hail_resistance_mm,
        wind_load_pa=wind_load_pa,
        snow_load_pa=snow_load_pa,
        source_url=None,
        source_name="测试目录",
        retrieved_at=datetime(2026, 9, 26, tzinfo=UTC),
        match_confidence=1.0,
    )


def weather(
    *,
    wind_m_s: float | None = 30,
    hail_mm: float | None = 20,
    snow_load_pa: float | None = 3000,
) -> WeatherProfile:
    return WeatherProfile(
        longitude=113.25,
        latitude=23.12,
        historical_max_wind_m_s=wind_m_s,
        historical_max_hail_mm=hail_mm,
        historical_max_snow_load_pa=snow_load_pa,
        observation_start=date(2021, 1, 1),
        observation_end=date(2025, 12, 31),
        source_name="测试气象源",
        source_url=None,
        retrieved_at=datetime(2026, 9, 26, tzinfo=UTC),
    )


def test_marks_complete_adequate_capacity_as_low_risk() -> None:
    result = CatastropheAssessmentEngine().assess(
        component=component(),
        weather=weather(),
    )

    assert result.resistance_level is ResistanceLevel.HIGH
    assert result.expected_loss_risk is ExpectedLossRisk.LOW
    assert result.requires_manual_review is False
    assert "CAT-WIND-CAPACITY-ADEQUATE" in result.triggered_rule_ids
    assert "CAT-HAIL-CAPACITY-ADEQUATE" in result.triggered_rule_ids
    assert "CAT-SNOW-CAPACITY-ADEQUATE" in result.triggered_rule_ids


def test_marks_capacity_shortfall_as_high_risk() -> None:
    result = CatastropheAssessmentEngine().assess(
        component=component(wind_load_pa=500),
        weather=weather(wind_m_s=35),
    )

    assert result.resistance_level is ResistanceLevel.LOW
    assert result.expected_loss_risk is ExpectedLossRisk.CRITICAL
    assert result.requires_manual_review is True
    assert "CAT-WIND-CRITICAL" in result.triggered_rule_ids


def test_marks_limited_margin_as_medium_risk() -> None:
    result = CatastropheAssessmentEngine().assess(
        component=component(hail_resistance_mm=22),
        weather=weather(hail_mm=20),
    )

    assert result.resistance_level is ResistanceLevel.MEDIUM
    assert result.expected_loss_risk is ExpectedLossRisk.MEDIUM
    assert result.requires_manual_review is True
    assert "CAT-HAIL-LIMITED-MARGIN" in result.triggered_rule_ids


def test_missing_hail_and_snow_data_remains_unknown() -> None:
    result = CatastropheAssessmentEngine().assess(
        component=component(),
        weather=weather(hail_mm=None, snow_load_pa=None),
    )

    assert result.resistance_level is ResistanceLevel.UNKNOWN
    assert result.expected_loss_risk is ExpectedLossRisk.UNKNOWN
    assert result.requires_manual_review is True
    assert "CAT-HAIL-DATA-MISSING" in result.triggered_rule_ids
    assert "CAT-SNOW-DATA-MISSING" in result.triggered_rule_ids
    assert any("缺少" in factor for factor in result.factors)


def test_missing_profiles_are_explicit() -> None:
    result = CatastropheAssessmentEngine().assess(component=None, weather=None)

    assert result.resistance_level is ResistanceLevel.UNKNOWN
    assert result.expected_loss_risk is ExpectedLossRisk.UNKNOWN
    assert result.requires_manual_review is True
    assert result.triggered_rule_ids == [
        "CAT-COMPONENT-PROFILE-MISSING",
        "CAT-WEATHER-PROFILE-MISSING",
    ]
