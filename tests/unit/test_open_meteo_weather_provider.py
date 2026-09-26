from datetime import UTC, date, datetime

import httpx
import pytest
from app.providers import ProviderError
from app.providers.weather import OpenMeteoWeatherProvider


def provider(
    handler,
) -> OpenMeteoWeatherProvider:
    return OpenMeteoWeatherProvider(
        observation_start=date(2021, 1, 1),
        observation_end=date(2025, 12, 31),
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
        clock=lambda: datetime(2026, 9, 26, 4, 0, tzinfo=UTC),
    )


def test_returns_maximum_historical_wind_and_request_parameters() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["latitude"] == "23.12"
        assert request.url.params["longitude"] == "113.25"
        assert request.url.params["start_date"] == "2021-01-01"
        assert request.url.params["end_date"] == "2025-12-31"
        assert request.url.params["daily"] == "wind_gusts_10m_max"
        assert request.url.params["timezone"] == "UTC"
        assert request.url.params["wind_speed_unit"] == "ms"
        return httpx.Response(
            200,
            json={
                "daily": {
                    "time": ["2025-01-01", "2025-01-02", "2025-01-03"],
                    "wind_gusts_10m_max": [18.5, None, 31.2],
                }
            },
        )

    result = provider(handler).lookup(longitude=113.25, latitude=23.12)

    assert result.historical_max_wind_m_s == 31.2
    assert result.historical_max_hail_mm is None
    assert result.historical_max_snow_load_pa is None
    assert result.observation_start == date(2021, 1, 1)
    assert result.observation_end == date(2025, 12, 31)
    assert result.source_name == "Open-Meteo Historical Weather API"
    assert result.retrieved_at == datetime(2026, 9, 26, 4, 0, tzinfo=UTC)


def test_all_null_wind_values_are_reported_as_missing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            json={
                "daily": {
                    "time": ["2025-01-01", "2025-01-02"],
                    "wind_gusts_10m_max": [None, None],
                }
            },
        )

    result = provider(handler).lookup(longitude=113.25, latitude=23.12)

    assert result.historical_max_wind_m_s is None


@pytest.mark.parametrize("status_code", [400, 429, 500])
def test_http_errors_are_sanitized(status_code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            status_code,
            json={"reason": "sensitive upstream details"},
        )

    with pytest.raises(ProviderError, match="weather provider request failed") as exc:
        provider(handler).lookup(longitude=113.25, latitude=23.12)

    assert "sensitive upstream details" not in str(exc.value)


def test_invalid_series_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            json={
                "daily": {
                    "time": ["2025-01-01"],
                    "wind_gusts_10m_max": [20.0, 30.0],
                }
            },
        )

    with pytest.raises(ProviderError, match="invalid response"):
        provider(handler).lookup(longitude=113.25, latitude=23.12)


def test_rejects_invalid_configuration() -> None:
    with pytest.raises(ValueError, match="observation_start"):
        OpenMeteoWeatherProvider(
            observation_start=date(2025, 1, 2),
            observation_end=date(2025, 1, 1),
        )

    with pytest.raises(ValueError, match="timeout_seconds"):
        OpenMeteoWeatherProvider(
            observation_start=date(2025, 1, 1),
            observation_end=date(2025, 1, 2),
            timeout_seconds=0,
        )
