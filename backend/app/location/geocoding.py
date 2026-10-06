"""Compatibility adapter for conservative location-evidence assessment."""

import os
from dataclasses import dataclass
from pathlib import Path

import httpx
from dotenv import load_dotenv

PROJECT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
AMAP_GEOCODING_URL = "https://restapi.amap.com/v3/geocode/geo"


@dataclass(frozen=True)
class GeocodeResult:
    longitude: float
    latitude: float
    level: str
    formatted_address: str
    precise: bool


class AmapGeocoder:
    """Select one Amap candidate for evidence comparison, without proving location."""

    URL = AMAP_GEOCODING_URL
    PRECISE_LEVELS = frozenset({"门牌号", "兴趣点", "楼宇"})

    def __init__(
        self,
        key: str,
        *,
        timeout_seconds: float = 8.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        from app.providers.geocoding import AmapGeocodingProvider

        self.key = key.strip()
        self.timeout_seconds = timeout_seconds
        self._provider = AmapGeocodingProvider(
            self.key,
            timeout_seconds=timeout_seconds,
            transport=transport,
        )

    @classmethod
    def from_environment(cls) -> "AmapGeocoder | None":
        load_dotenv(PROJECT_ENV_PATH, override=False)
        key = os.getenv("PV_AMAP_WEB_SERVICE_KEY", "").strip()
        return cls(key) if key else None

    def lookup(self, address: str, *, city: str | None = None) -> GeocodeResult | None:
        from app.providers.common import ProviderError

        try:
            matches = self._provider.lookup(address, city=city)
        except (ProviderError, ValueError):
            return None
        if len(matches) != 1:
            return None
        match = matches[0]
        return GeocodeResult(
            longitude=match.amap_longitude,
            latitude=match.amap_latitude,
            level=match.level,
            formatted_address=match.formatted_address,
            precise=match.level in self.PRECISE_LEVELS,
        )
