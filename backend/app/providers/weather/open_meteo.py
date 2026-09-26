from collections.abc import Callable
from datetime import UTC, date, datetime
from math import isfinite
from typing import Self

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from app.contracts import WeatherProfile

from ..common import ProviderError
from .base import WeatherProvider

OPEN_METEO_SOURCE_URL = "https://open-meteo.com/en/docs/historical-weather-api"


class _DailyWeather(BaseModel):
    model_config = ConfigDict(extra="ignore")

    time: list[date]
    wind_gusts_10m_max: list[float | None]

    @model_validator(mode="after")
    def validate_series_lengths(self) -> Self:
        if len(self.time) != len(self.wind_gusts_10m_max):
            raise ValueError("daily weather series lengths do not match")
        return self


class _OpenMeteoResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    daily: _DailyWeather


class OpenMeteoWeatherProvider(WeatherProvider):
    """通过 Open-Meteo 历史气象 API 查询最大阵风。"""

    def __init__(
        self,
        *,
        observation_start: date,
        observation_end: date,
        base_url: str = "https://archive-api.open-meteo.com/v1/archive",
        timeout_seconds: float = 30.0,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if observation_start > observation_end:
            raise ValueError("observation_start must not be after observation_end")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not base_url.startswith(("https://", "http://")):
            raise ValueError("base_url must be an HTTP URL")

        self.observation_start = observation_start
        self.observation_end = observation_end
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.transport = transport
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def name(self) -> str:
        return "open-meteo-historical-weather"

    def lookup(
        self,
        *,
        longitude: float,
        latitude: float,
    ) -> WeatherProfile:
        if not -180.0 <= longitude <= 180.0:
            raise ValueError("longitude is outside the valid range")
        if not -90.0 <= latitude <= 90.0:
            raise ValueError("latitude is outside the valid range")

        try:
            with httpx.Client(
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = client.get(
                    self.base_url,
                    params={
                        "latitude": latitude,
                        "longitude": longitude,
                        "start_date": self.observation_start.isoformat(),
                        "end_date": self.observation_end.isoformat(),
                        "daily": "wind_gusts_10m_max",
                        "timezone": "UTC",
                        "wind_speed_unit": "ms",
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError("weather provider request failed") from exc

        try:
            payload = _OpenMeteoResponse.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise ProviderError("weather provider returned an invalid response") from exc

        wind_values = [
            value
            for value in payload.daily.wind_gusts_10m_max
            if value is not None and isfinite(value) and value >= 0.0
        ]

        return WeatherProfile(
            longitude=longitude,
            latitude=latitude,
            historical_max_wind_m_s=max(wind_values, default=None),
            historical_max_hail_mm=None,
            historical_max_snow_load_pa=None,
            observation_start=self.observation_start,
            observation_end=self.observation_end,
            source_name="Open-Meteo Historical Weather API",
            source_url=OPEN_METEO_SOURCE_URL,
            retrieved_at=self._clock(),
        )
