"""Optional address lookup. A result is a candidate, never proof of a site's location."""

import os
from dataclasses import dataclass
from pathlib import Path

import httpx
from dotenv import dotenv_values

SHARED_ENV_PATH = Path.home() / "Documents" / "软件开发知识" / ".env"


@dataclass(frozen=True)
class GeocodeResult:
    longitude: float
    latitude: float
    level: str
    formatted_address: str
    precise: bool


class AmapGeocoder:
    """Use a server-side Amap Web Service key; never expose it to the browser."""

    URL = "https://restapi.amap.com/v3/geocode/geo"
    PRECISE_LEVELS = frozenset({"门牌号", "兴趣点", "楼宇"})

    def __init__(self, key: str, *, timeout_seconds: float = 8.0) -> None:
        self.key = key
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_environment(cls) -> "AmapGeocoder | None":
        key = os.getenv("PV_AMAP_WEB_KEY", "").strip()
        if not key and SHARED_ENV_PATH.is_file():
            key = (dotenv_values(SHARED_ENV_PATH).get("PV_AMAP_WEB_KEY") or "").strip()
        return cls(key) if key else None

    def lookup(self, address: str, *, city: str | None = None) -> GeocodeResult | None:
        params = {"key": self.key, "address": address, "output": "JSON"}
        if city:
            params["city"] = city
        try:
            response = httpx.get(self.URL, params=params, timeout=self.timeout_seconds)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                return None
            if payload.get("status") != "1":
                return None
            matches = payload.get("geocodes") or []
            # Several possible places must be resolved by a human.
            if len(matches) != 1:
                return None
            item = matches[0]
            longitude, latitude = (float(value) for value in item["location"].split(","))
            if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
                return None
            level = item.get("level", "")
            return GeocodeResult(
                longitude=longitude,
                latitude=latitude,
                level=level,
                formatted_address=item.get("formatted_address", ""),
                precise=level in self.PRECISE_LEVELS,
            )
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return None
