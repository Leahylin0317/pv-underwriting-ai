"""Local-first lookup must never turn search leads into load values."""

from datetime import UTC, date, datetime

import httpx
import pytest
from app.catastrophe import CatastropheAssessmentEngine
from app.contracts import (
    ComponentProfile,
    Material,
    MaterialCategory,
    MaterialParseStatus,
    MaterialQualityStatus,
    ProjectInfo,
)
from app.pipeline import UnderwritingPipeline
from app.providers import MaterialInput, MockOcrProvider, MockVisionProvider
from app.providers.common import ProviderError
from app.providers.component import (
    CatalogComponentProvider,
    LocalFirstComponentProvider,
    RemoteCatalogComponentProvider,
)
from app.providers.weather import OpenMeteoWeatherProvider

_URL = "https://catalog.example.test/components"


def profile(model: str, **updates: object) -> ComponentProfile:
    data: dict[str, object] = {
        "component_model": model,
        "manufacturer": "JA Solar",
        "rated_power_w": 630,
        "hail_resistance_mm": None,
        "wind_load_pa": None,
        "snow_load_pa": None,
        "source_url": "https://www.jasolar.com/local.pdf",
        "source_name": "reviewed local record",
        "retrieved_at": datetime(2026, 9, 1, tzinfo=UTC),
        "match_confidence": 0.9,
    }
    data.update(updates)
    return ComponentProfile.model_validate(data)


def remote(
    response: httpx.Response,
    calls: list[str],
) -> RemoteCatalogComponentProvider:
    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.params["model"])
        return response

    return RemoteCatalogComponentProvider(
        _URL,
        approved_source_domains=("jasolar.com",),
        transport=httpx.MockTransport(respond),
    )


def verified(model: str, **updates: object) -> httpx.Response:
    values: dict[str, object] = {
        "source_url": "https://www.jasolar.com/verified.pdf",
        "source_name": "official verified datasheet",
        "wind_load_pa": 1600,
        "parameter_sources": {
            "rated_power_w": "https://www.jasolar.com/verified.pdf",
            "wind_load_pa": "https://www.jasolar.com/verified.pdf",
        },
    }
    values.update(updates)
    return httpx.Response(
        200,
        json={
            "verified": True,
            "profile": profile(model, **values).model_dump(mode="json"),
        },
    )


def test_complete_local_record_never_calls_online() -> None:
    calls: list[str] = []
    local = CatalogComponentProvider(
        [profile("MODEL-1", hail_resistance_mm=25, wind_load_pa=2400, snow_load_pa=5400)]
    )
    provider = LocalFirstComponentProvider(local, remote(verified("MODEL-1"), calls))

    assert provider.lookup("MODEL-1").wind_load_pa == 2400
    assert calls == []


def test_missing_local_parameter_is_filled_with_online_provenance() -> None:
    calls: list[str] = []
    local = CatalogComponentProvider([profile("JAM72D42-630/LB")])
    provider = LocalFirstComponentProvider(
        local, remote(verified("JAM72D42-630/LB"), calls)
    )

    result = provider.lookup("JAM72D42-630/LB")

    assert result is not None
    assert result.rated_power_w == 630
    assert result.wind_load_pa == 1600
    assert result.hail_resistance_mm is None
    assert result.parameter_sources["rated_power_w"] == "https://www.jasolar.com/local.pdf"
    assert result.parameter_sources["wind_load_pa"] == "https://www.jasolar.com/verified.pdf"
    assert calls == ["JAM72D42-630/LB"]


def test_online_exact_model_can_supply_new_record() -> None:
    calls: list[str] = []
    provider = LocalFirstComponentProvider(
        CatalogComponentProvider([]), remote(verified("MODEL-NEW"), calls)
    )

    assert provider.lookup("MODEL-NEW").wind_load_pa == 1600
    assert calls == ["MODEL-NEW"]


def test_online_variant_mismatch_cannot_fill_local_gaps() -> None:
    calls: list[str] = []
    online = remote(verified("JAM72D42-630/LB"), calls)

    with pytest.raises(ProviderError, match="unverified data"):
        online.lookup("JAM72D42-630W")

    local = CatalogComponentProvider([profile("JAM72D42-630W")])
    result = LocalFirstComponentProvider(local, online).lookup("JAM72D42-630W")
    assert result is not None
    assert result.wind_load_pa is None


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json={"verified": False, "profile": {}}),
        httpx.Response(302, headers={"Location": "https://evil.test/"}),
        verified("MODEL-NEW", source_url="https://jasolar.com.evil.test/spec.pdf"),
    ],
)
def test_unverified_or_redirected_data_is_rejected(response: httpx.Response) -> None:
    with pytest.raises(ProviderError):
        remote(response, []).lookup("MODEL-NEW")


def test_online_404_keeps_local_unknown() -> None:
    local = CatalogComponentProvider([profile("MODEL-1")])
    provider = LocalFirstComponentProvider(local, remote(httpx.Response(404), []))

    assert provider.lookup("MODEL-1").wind_load_pa is None


def test_online_error_preserves_local_data_and_marks_gap() -> None:
    local = CatalogComponentProvider([profile("MODEL-1")])
    provider = LocalFirstComponentProvider(local, remote(httpx.Response(503), []))

    result = provider.lookup("MODEL-1")

    assert result.rated_power_w == 630
    assert result.wind_load_pa is None
    assert result.lookup_notes == ["在线组件目录查询失败，缺失参数未补齐"]


def test_ocr_model_flows_through_online_fallback_and_weather_assessment() -> None:
    calls: list[str] = []
    component_provider = LocalFirstComponentProvider(
        CatalogComponentProvider([]),
        remote(verified("JAM66D42-580/MB"), calls),
    )

    def weather_response(request: httpx.Request) -> httpx.Response:
        assert request.url.params["latitude"] == "23.12"
        return httpx.Response(
            200,
            json={
                "daily": {
                    "time": ["2026-09-01"],
                    "wind_gusts_10m_max": [30.0],
                    "snowfall_sum": [0.0],
                }
            },
        )

    pipeline = UnderwritingPipeline(
        ocr_provider=MockOcrProvider(),
        vision_provider=MockVisionProvider(),
        component_provider=component_provider,
        weather_provider=OpenMeteoWeatherProvider(
            observation_start=date(2026, 9, 1),
            observation_end=date(2026, 9, 1),
            transport=httpx.MockTransport(weather_response),
        ),
        catastrophe_engine=CatastropheAssessmentEngine(),
    )
    material = Material(
        material_id="nameplate-1",
        category=MaterialCategory.COMPONENT_NAMEPLATE,
        file_name="nameplate.jpg",
        media_type="image/jpeg",
        quality_status=MaterialQualityStatus.USABLE,
        quality_issues=[],
        parse_status=MaterialParseStatus.SUCCESS,
    )
    case = pipeline.run(
        case_id="case-online-fallback",
        project=ProjectInfo(
            project_name="核保测试",
            insured_name="示例企业",
            project_type="rooftop",
            installation_type="color_steel_roof",
            site_address="示例地址",
            longitude=113.25,
            latitude=23.12,
            proposed_start_date=None,
            component_model=None,
        ),
        materials=[MaterialInput(material=material, content=b"test-image")],
    )

    assert case.project.component_model == "JAM66D42-580/MB"
    assert calls == ["JAM66D42-580/MB"]
    assert case.component_profile.wind_load_pa == 1600
    assert case.weather_profile.historical_max_wind_m_s == 30.0
    assert "CAT-WIND-CAPACITY-ADEQUATE" in (
        case.catastrophe_assessment.triggered_rule_ids
    )
    assert case.catastrophe_assessment.requires_manual_review is True
