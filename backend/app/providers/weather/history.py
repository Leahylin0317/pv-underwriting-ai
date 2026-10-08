"""Historical weather series for a site, with explicit data-source limitations."""

from collections import defaultdict
from datetime import UTC, date, datetime
from math import isfinite

import httpx

from app.providers.common import ProviderError

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
MAIN_FIELDS = (
    "wind_speed_10m",
    "wind_gusts_10m",
    "wind_direction_10m",
    "temperature_2m",
    "surface_pressure",
    "precipitation",
    "rain",
    "snowfall",
)


def _number(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value):
        return float(value)
    return None


def _maximum(values: list[float | None]) -> float | None:
    valid = [value for value in values if value is not None]
    return max(valid) if valid else None


def _minimum(values: list[float | None]) -> float | None:
    valid = [value for value in values if value is not None]
    return min(valid) if valid else None


def _sum(values: list[float | None]) -> float | None:
    valid = [value for value in values if value is not None]
    return round(sum(valid), 3) if valid else None


class HistoricalWeatherClient:
    """Query a fixed reanalysis model; keep null values distinct from zero."""

    def __init__(
        self,
        *,
        base_url: str = ARCHIVE_URL,
        timeout_seconds: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def _fetch(
        self,
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
        *,
        model: str,
        fields: tuple[str, ...],
    ) -> dict:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "models": model,
            "hourly": ",".join(fields),
            "timezone": "Asia/Shanghai",
            "wind_speed_unit": "ms",
            "precipitation_unit": "mm",
        }
        try:
            with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
                response = client.get(self.base_url, params=params)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError("historical weather request failed") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("hourly"), dict):
            raise ProviderError("historical weather response is invalid")
        series = payload["hourly"]
        times = series.get("time")
        if not isinstance(times, list) or not times:
            raise ProviderError("historical weather response has no time series")
        for field in fields:
            if not isinstance(series.get(field), list) or len(series[field]) != len(times):
                raise ProviderError("historical weather response has mismatched fields")
        if not isinstance(payload.get("hourly_units"), dict):
            raise ProviderError("historical weather response has no units")
        return payload

    def lookup(
        self,
        *,
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
        resolution: str = "daily",
    ) -> dict:
        main = self._fetch(
            latitude, longitude, start_date, end_date,
            model="era5", fields=MAIN_FIELDS,
        )
        # Ground snow depth is available from ERA5-Land, on a different grid.
        snow_error = None
        try:
            snow = self._fetch(
                latitude, longitude, start_date, end_date,
                model="era5_land", fields=("snow_depth",),
            )
        except ProviderError:
            snow = None
            snow_error = "ERA5-Land snow depth could not be retrieved"

        main_hourly = main["hourly"]
        snow_by_time = (
            dict(zip(snow["hourly"]["time"], snow["hourly"]["snow_depth"]))
            if snow else {}
        )
        hours: list[dict] = []
        for index, timestamp in enumerate(main_hourly["time"]):
            try:
                parsed = datetime.fromisoformat(timestamp)
            except (TypeError, ValueError) as exc:
                raise ProviderError("historical weather response has invalid times") from exc
            row = {field: _number(main_hourly[field][index]) for field in MAIN_FIELDS}
            row["snow_depth"] = _number(snow_by_time.get(timestamp))
            row["time"] = timestamp
            row["date"] = parsed.date().isoformat()
            hours.append(row)

        by_day: dict[str, list[dict]] = defaultdict(list)
        for row in hours:
            by_day[row["date"]].append(row)
        days = [self._aggregate(day, rows) for day, rows in sorted(by_day.items())]
        by_year: dict[str, list[dict]] = defaultdict(list)
        for row in hours:
            by_year[row["date"][:4]].append(row)
        years = [self._aggregate(year, rows) for year, rows in sorted(by_year.items())]

        units = {
            **main["hourly_units"],
            "snow_depth": snow["hourly_units"].get("snow_depth", "m") if snow else "m",
        }
        expected_hours = ((end_date - start_date).days + 1) * 24
        unique_hours = len({row["time"] for row in hours})
        wind_gust_non_null = sum(row["wind_gusts_10m"] is not None for row in hours)
        return {
            "requested_coordinates": {"latitude": latitude, "longitude": longitude, "system": "WGS84"},
            "period": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
            "timezone": "Asia/Shanghai",
            "resolution": resolution,
            "retrieved_at": datetime.now(UTC).isoformat(),
            "sources": {
                "wind_rain_snowfall": {
                    "provider": "Open-Meteo Historical Weather API", "model": "era5",
                    "url": self.base_url,
                    "grid_latitude": main.get("latitude"), "grid_longitude": main.get("longitude"),
                },
                "ground_snow_depth": {
                    "provider": "Open-Meteo Historical Weather API", "model": "era5_land",
                    "url": self.base_url,
                    "grid_latitude": snow.get("latitude") if snow else None,
                    "grid_longitude": snow.get("longitude") if snow else None,
                    "status": "available" if snow and any(row["snow_depth"] is not None for row in hours)
                    else "unavailable",
                    "note": snow_error or "Ground snow depth is not rooftop snow load",
                },
            },
            "units": units,
            "quality": {
                "hours": len(hours),
                "expected_hours": expected_hours,
                "unique_hours": unique_hours,
                "time_series_complete": len(hours) == expected_hours and unique_hours == expected_hours,
                "wind_gust_non_null_hours": wind_gust_non_null,
                "wind_gust_complete": wind_gust_non_null == expected_hours,
                "ground_snow_depth_non_null_hours": sum(row["snow_depth"] is not None for row in hours),
                "note": "Reanalysis grid values are not site measurements; ERA5 gust provenance requires verification",
            },
            "hail": {
                "status": "unavailable", "event_count": None, "max_diameter_mm": None,
                "note": "No verified historical hail-event or diameter provider is configured; missing is not zero",
            },
            "data": hours if resolution == "hourly" else days if resolution == "daily" else years,
        }

    @staticmethod
    def _aggregate(period: str, rows: list[dict]) -> dict:
        def values(field: str) -> list[float | None]:
            return [row[field] for row in rows]

        return {
            "period": period,
            "hours": len(rows),
            "valid_hours": {
                field: sum(value is not None for value in values(field))
                for field in MAIN_FIELDS + ("snow_depth",)
            },
            "wind_speed_10m_max": _maximum(values("wind_speed_10m")),
            "wind_gusts_10m_max": _maximum(values("wind_gusts_10m")),
            "wind_gusts_10m_valid_hours": sum(value is not None for value in values("wind_gusts_10m")),
            "temperature_2m_min": _minimum(values("temperature_2m")),
            "temperature_2m_max": _maximum(values("temperature_2m")),
            "surface_pressure_mean": (
                round(sum(v for v in values("surface_pressure") if v is not None)
                      / sum(v is not None for v in values("surface_pressure")), 3)
                if any(v is not None for v in values("surface_pressure")) else None
            ),
            "precipitation_sum": _sum(values("precipitation")),
            "rain_sum": _sum(values("rain")),
            "snowfall_sum": _sum(values("snowfall")),
            "ground_snow_depth_max": _maximum(values("snow_depth")),
        }
