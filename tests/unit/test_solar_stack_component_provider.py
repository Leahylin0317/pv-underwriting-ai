from __future__ import annotations

import httpx
import pytest
from app.providers.common import ProviderError
from app.providers.component import SolarStackPartnerApiComponentProvider


def listing(*rows: dict[str, object]) -> httpx.Response:
    return httpx.Response(200, json={"data": list(rows), "meta": {"total": len(rows)}})


def candidate(model: str, *, item_id: str = "module-1", manufacturer: str = "LONGi") -> dict[str, object]:
    return {"id": item_id, "name": model, "manufacturer": manufacturer}


def detail(
    model: str,
    *,
    manufacturer: str = "LONGi",
    series: dict[str, object] | None = None,
    datasheets: list[dict[str, object]] | None = None,
) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "data": {
                "id": "module-1",
                "name": model,
                "manufacturer": manufacturer,
                "pmax": 615,
                "url": f"https://www.solar-stack.com/en/panel/longi/{model.lower()}",
                "series": {
                    "name": "Example Series",
                    "markets": ["GLOBAL"],
                    "sourceUrl": "https://www.longi.com/en/products/modules/",
                    "maxLoadFrontPa": 5400,
                    "maxLoadRearPa": 2400,
                    "hailDiameterMm": 25,
                    "hailSpeedMs": 23,
                    **(series or {}),
                },
                "datasheets": datasheets
                if datasheets is not None
                else [
                    {
                        "type": "datasheet",
                        "fileName": "module.pdf",
                        "url": "https://files.example.test/module.pdf",
                    }
                ],
            }
        },
    )


def provider(handler) -> SolarStackPartnerApiComponentProvider:
    return SolarStackPartnerApiComponentProvider(
        "test-secret",
        transport=httpx.MockTransport(handler),
    )


def test_exact_global_model_maps_only_fields_supported_by_partner_api() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["Authorization"] == "Bearer test-secret"
        if request.url.path == "/v1/panels":
            assert request.url.params["market"] == "GLOBAL"
            assert request.url.params["search"] == "LR8-66HGD-615M"
            return listing(candidate("LR8-66HGD-615M"))
        return detail("LR8-66HGD-615M")

    result = provider(respond).lookup(" LR8‑66HGD‑615M ")

    assert result is not None
    assert result.component_model == "LR8-66HGD-615M"
    assert result.manufacturer == "LONGi"
    assert result.rated_power_w == 615
    assert result.hail_resistance_mm == 25
    assert result.hail_impact_velocity_m_s == 23
    assert result.front_static_load_pa == 5400
    assert result.back_static_load_pa == 2400
    assert result.wind_load_pa is None
    assert result.snow_load_pa is None
    assert result.source_name == "Solar Stack Partner API"
    assert result.parameter_sources["hail_resistance_mm"].endswith("module.pdf")
    assert len(requests) == 2


def test_near_model_match_is_not_accepted() -> None:
    provider_instance = provider(
        lambda request: listing(candidate("LR8-66HGD-615"))
    )

    assert provider_instance.lookup("LR8-66HGD-615M") is None


def test_ambiguous_exact_names_are_not_selected_without_manufacturer() -> None:
    provider_instance = provider(
        lambda request: listing(
            candidate("SAME-MODEL", item_id="first", manufacturer="LONGi"),
            candidate("SAME-MODEL", item_id="second", manufacturer="Trina"),
        )
    )

    assert provider_instance.lookup("SAME-MODEL") is None


def test_cached_result_avoids_repeated_api_calls_and_returns_a_copy() -> None:
    paths: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/v1/panels":
            return listing(candidate("MODEL-1"))
        return detail("MODEL-1")

    provider_instance = provider(respond)
    first = provider_instance.lookup("MODEL-1")
    first.lookup_notes.append("caller mutation")
    second = provider_instance.lookup("MODEL-1")

    assert second is not None
    assert "caller mutation" not in second.lookup_notes
    assert paths == ["/v1/panels", "/v1/panels/module-1"]


def test_upstream_errors_are_sanitized() -> None:
    provider_instance = provider(
        lambda request: httpx.Response(401, text="credential rejected")
    )

    with pytest.raises(ProviderError, match="Solar Stack Partner API request failed") as error:
        provider_instance.lookup("MODEL-1")
    assert "test-secret" not in str(error.value)


def test_multiple_datasheets_link_to_model_page_until_edition_is_confirmed() -> None:
    provider_instance = provider(
        lambda request: listing(candidate("MODEL-1"))
        if request.url.path == "/v1/panels"
        else detail(
            "MODEL-1",
            datasheets=[
                {"type": "datasheet", "url": "https://files.example.test/a.pdf"},
                {"type": "datasheet", "url": "https://files.example.test/b.pdf"},
            ],
        )
    )

    result = provider_instance.lookup("MODEL-1")

    assert result is not None
    assert result.parameter_sources["rated_power_w"] == result.source_url
    assert any("多个 Datasheet 版本" in note for note in result.lookup_notes)
