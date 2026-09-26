from datetime import UTC, date, datetime

from app.catastrophe import CatastropheAssessmentEngine
from app.contracts import (
    ComponentProfile,
    ProcessingStatus,
    ProcessingStep,
    ProjectInfo,
    WeatherProfile,
)
from app.pipeline import UnderwritingPipeline
from app.providers import MockOcrProvider, MockVisionProvider, ProviderError
from app.providers.component import CatalogComponentProvider
from app.providers.weather import WeatherProvider


def project_info() -> ProjectInfo:
    return ProjectInfo(
        project_name="气象流水线测试",
        insured_name="示例企业",
        project_type="rooftop",
        installation_type="color_steel_roof",
        site_address="广东省广州市",
        longitude=113.25,
        latitude=23.12,
        proposed_start_date="2026-10-01",
        component_model="PV-MODULE-580W",
    )


def component_profile() -> ComponentProfile:
    return ComponentProfile(
        component_model="PV-MODULE-580W",
        manufacturer="示例厂商",
        rated_power_w=580,
        hail_resistance_mm=25,
        wind_load_pa=2400,
        snow_load_pa=5400,
        source_url=None,
        source_name="测试组件目录",
        retrieved_at=datetime(2026, 9, 26, tzinfo=UTC),
        match_confidence=1.0,
    )


def weather_profile() -> WeatherProfile:
    return WeatherProfile(
        longitude=113.25,
        latitude=23.12,
        historical_max_wind_m_s=30,
        historical_max_hail_mm=20,
        historical_max_snow_load_pa=3000,
        observation_start=date(2021, 1, 1),
        observation_end=date(2025, 12, 31),
        source_name="测试气象源",
        source_url=None,
        retrieved_at=datetime(2026, 9, 26, tzinfo=UTC),
    )


class StaticWeatherProvider(WeatherProvider):
    @property
    def name(self) -> str:
        return "static-weather"

    def lookup(self, *, longitude: float, latitude: float) -> WeatherProfile:
        assert longitude == 113.25
        assert latitude == 23.12
        return weather_profile()


class FailingWeatherProvider(WeatherProvider):
    @property
    def name(self) -> str:
        return "failing-weather"

    def lookup(self, *, longitude: float, latitude: float) -> WeatherProfile:
        del longitude, latitude
        raise ProviderError("sensitive weather upstream details")


def pipeline(weather_provider: WeatherProvider) -> UnderwritingPipeline:
    return UnderwritingPipeline(
        ocr_provider=MockOcrProvider(),
        vision_provider=MockVisionProvider(),
        component_provider=CatalogComponentProvider([component_profile()]),
        weather_provider=weather_provider,
        catastrophe_engine=CatastropheAssessmentEngine(),
    )


def test_pipeline_adds_weather_and_catastrophe_results() -> None:
    case = pipeline(StaticWeatherProvider()).run(
        case_id="case-weather-001",
        project=project_info(),
        materials=[],
    )

    assert case.weather_profile is not None
    assert case.weather_profile.historical_max_wind_m_s == 30
    assert case.catastrophe_assessment is not None
    assert case.catastrophe_assessment.requires_manual_review is False

    steps = [trace.step for trace in case.processing_trace]
    assert ProcessingStep.WEATHER_LOOKUP in steps
    assert ProcessingStep.CATASTROPHE_ASSESSMENT in steps
    assert len(case.processing_trace) == 7


def test_weather_failure_is_sanitized_and_pipeline_continues() -> None:
    case = pipeline(FailingWeatherProvider()).run(
        case_id="case-weather-002",
        project=project_info(),
        materials=[],
    )

    assert case.weather_profile is None
    assert case.catastrophe_assessment is not None
    assert case.catastrophe_assessment.requires_manual_review is True

    trace = next(
        item
        for item in case.processing_trace
        if item.step is ProcessingStep.WEATHER_LOOKUP
    )
    assert trace.status is ProcessingStatus.FAILED
    assert trace.error_code == "WEATHER_PROVIDER_FAILURE"
    assert trace.error_message == "weather provider lookup failed"
    assert "sensitive weather upstream details" not in trace.error_message
    assert case.decision is not None
    assert "SYS-PROVIDER-FAILURE" in case.decision.decisive_rule_ids
    assert "CAT-WEATHER-PROFILE-MISSING" in case.decision.decisive_rule_ids
