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
    snowfall_cm: float | None = None,
) -> WeatherProfile:
    return WeatherProfile(
        longitude=113.25,
        latitude=23.12,
        historical_max_wind_m_s=wind_m_s,
        historical_max_hail_mm=hail_mm,
        historical_max_snow_load_pa=snow_load_pa,
        historical_max_daily_snowfall_cm=snowfall_cm,
        observation_start=date(2021, 1, 1),
        observation_end=date(2025, 12, 31),
        source_name="测试气象源",
        source_url=None,
        retrieved_at=datetime(2026, 9, 26, tzinfo=UTC),
    )


def test_reports_complete_metrics_without_claiming_unverified_comparability() -> None:
    result = CatastropheAssessmentEngine().assess(
        component=component(),
        weather=weather(),
    )

    assert result.resistance_level is ResistanceLevel.UNKNOWN
    assert result.expected_loss_risk is ExpectedLossRisk.UNKNOWN
    assert result.requires_manual_review is True
    assert result.critical_shortfall_ratio is None
    assert result.adequate_margin_ratio is None
    assert "CAT-WIND-COMPARABILITY-UNVERIFIED" in result.triggered_rule_ids
    assert "CAT-HAIL-COMPARABILITY-UNVERIFIED" in result.triggered_rule_ids
    assert "CAT-SNOW-COMPARABILITY-UNVERIFIED" in result.triggered_rule_ids
    assert "CAT-INSTALL-WIND-APPLICABILITY-PENDING" in result.triggered_rule_ids
    assert "CAT-INSTALL-HAIL-APPLICABILITY-PENDING" in result.triggered_rule_ids
    assert "CAT-INSTALL-SNOW-APPLICABILITY-PENDING" in result.triggered_rule_ids
    assert len(result.installation_parameter_reviews) == 3
    assert all(review.status.value == "pending_confirmation" for review in result.installation_parameter_reviews)
    assert any("10米历史阵风不是屋面项目设计风压" in factor for factor in result.factors)


def test_does_not_turn_historic_gust_pressure_into_false_critical_risk() -> None:
    result = CatastropheAssessmentEngine().assess(
        component=component(wind_load_pa=500),
        weather=weather(wind_m_s=35),
    )

    assert result.resistance_level is ResistanceLevel.UNKNOWN
    assert result.expected_loss_risk is ExpectedLossRisk.UNKNOWN
    assert result.requires_manual_review is True
    assert "CAT-WIND-COMPARABILITY-UNVERIFIED" in result.triggered_rule_ids


def test_does_not_compare_hail_diameter_without_a_compatible_event_basis() -> None:
    result = CatastropheAssessmentEngine().assess(
        component=component(hail_resistance_mm=22),
        weather=weather(hail_mm=20),
    )

    assert result.resistance_level is ResistanceLevel.UNKNOWN
    assert result.expected_loss_risk is ExpectedLossRisk.UNKNOWN
    assert result.requires_manual_review is True
    assert "CAT-HAIL-COMPARABILITY-UNVERIFIED" in result.triggered_rule_ids


def test_missing_hail_and_snow_data_remains_unknown() -> None:
    result = CatastropheAssessmentEngine().assess(
        component=component(),
        weather=weather(hail_mm=None, snow_load_pa=None),
    )

    assert result.resistance_level is ResistanceLevel.UNKNOWN
    assert result.expected_loss_risk is ExpectedLossRisk.UNKNOWN
    assert result.requires_manual_review is True
    assert "CAT-HAIL-WEATHER-DATA-MISSING" in result.triggered_rule_ids
    assert "CAT-SNOW-WEATHER-DATA-MISSING" in result.triggered_rule_ids
    assert "CAT-HAIL-COMPARABILITY-UNVERIFIED" in result.triggered_rule_ids
    assert "CAT-SNOW-COMPARABILITY-UNVERIFIED" in result.triggered_rule_ids
    assert any("人工复核事项" in factor for factor in result.factors)


def test_snowfall_indicator_is_reported_without_being_misrepresented_as_load() -> None:
    result = CatastropheAssessmentEngine().assess(
        component=component(),
        weather=weather(hail_mm=None, snow_load_pa=None, snowfall_cm=18.0),
    )

    assert result.expected_loss_risk is ExpectedLossRisk.UNKNOWN
    assert any("18.0 cm" in factor and "不换算为屋面或组件结构雪荷载" in factor for factor in result.factors)
    assert "CAT-SNOW-WEATHER-DATA-MISSING" in result.triggered_rule_ids


def test_missing_profiles_are_explicit() -> None:
    result = CatastropheAssessmentEngine().assess(component=None, weather=None)

    assert result.resistance_level is ResistanceLevel.UNKNOWN
    assert result.expected_loss_risk is ExpectedLossRisk.UNKNOWN
    assert result.requires_manual_review is True
    assert result.triggered_rule_ids == [
        "CAT-INSTALL-WIND-APPLICABILITY-PENDING",
        "CAT-INSTALL-HAIL-APPLICABILITY-PENDING",
        "CAT-INSTALL-SNOW-APPLICABILITY-PENDING",
        "CAT-COMPONENT-PROFILE-MISSING",
        "CAT-WEATHER-PROFILE-MISSING",
    ]


def test_zero_hail_and_snow_demand_do_not_divide_by_zero():
    engine=CatastropheAssessmentEngine()
    source=weather(hail_mm=0,snow_load_pa=0)
    result=engine.assess(component=component(),weather=source)
    assert result.expected_loss_risk is ExpectedLossRisk.UNKNOWN
    rows=engine.comparisons(component(),source)
    assert [r['status'] for r in rows]==['calculated','insufficient','insufficient']
    assert rows[1]['ratio'] is None


def test_detailed_ratios_match_engine_thresholds():
    engine=CatastropheAssessmentEngine()
    c=component(wind_load_pa=0.613*30**2)
    rows=engine.comparisons(c,weather())
    assert rows[0]['ratio']==1
    assert rows[0]['risk']=='medium'
    assert rows[0]['rule_ids']==['CAT-WIND-LIMITED-MARGIN']
    assert engine.assess(component=c,weather=weather()).expected_loss_risk is ExpectedLossRisk.UNKNOWN
