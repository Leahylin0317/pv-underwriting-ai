"""Exact-model lookup through the Solar Stack read-only Partner API."""

from __future__ import annotations

import math
import unicodedata
from datetime import UTC, datetime
from threading import Lock
from time import monotonic
from urllib.parse import urlparse

import httpx

from app.contracts import ComponentProfile
from app.providers.common import ProviderError

from .base import ComponentProvider
from .catalog import normalize_component_model

_BASE_URL = "https://partner-api.solar-stack.com"
_API_HOST = "partner-api.solar-stack.com"
_MAX_RESPONSE_BYTES = 2_000_000
_CACHE_TTL_SECONDS = 24 * 60 * 60


def _api_search_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).strip()
    for dash in "‐‑‒–—―−﹘﹣－":
        text = text.replace(dash, "-")
    return text


def _https_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return None
    return value


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        return None
    result = float(value)
    return result if math.isfinite(result) and result > 0 else None


class SolarStackPartnerApiComponentProvider(ComponentProvider):
    """Fetch exact GLOBAL-market module records and cache them in process.

    Search snippets and near matches are never converted into parameters. If
    the API returns multiple exact-model rows, the provider declines to choose
    one because the submitted project has not identified the manufacturer.
    """

    def __init__(
        self,
        api_key: str,
        *,
        timeout_seconds: float = 15.0,
        cache_ttl_seconds: float = _CACHE_TTL_SECONDS,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Solar Stack API key is required")
        if timeout_seconds <= 0 or cache_ttl_seconds <= 0:
            raise ValueError("Solar Stack timeout and cache TTL must be positive")
        parsed = urlparse(_BASE_URL)
        if parsed.scheme != "https" or parsed.hostname != _API_HOST:
            raise ValueError("Solar Stack API endpoint is invalid")
        self._api_key = api_key.strip()
        self._timeout_seconds = timeout_seconds
        self._cache_ttl_seconds = cache_ttl_seconds
        self._transport = transport
        self._cache: dict[str, tuple[float, ComponentProfile | None]] = {}
        self._cache_lock = Lock()

    @property
    def name(self) -> str:
        return "solar-stack-partner-api"

    def lookup(self, component_model: str) -> ComponentProfile | None:
        normalized = normalize_component_model(component_model)
        if not normalized:
            return None
        now = monotonic()
        with self._cache_lock:
            cached = self._cache.get(normalized)
            if cached is not None and cached[0] > now:
                return cached[1].model_copy(deep=True) if cached[1] is not None else None

        result = self._lookup_exact(component_model.strip(), normalized)
        with self._cache_lock:
            cached_result = result.model_copy(deep=True) if result is not None else None
            self._cache[normalized] = (now + self._cache_ttl_seconds, cached_result)
        return result.model_copy(deep=True) if result is not None else None

    def _lookup_exact(self, model: str, normalized: str) -> ComponentProfile | None:
        listing = self._get_json(
            "/v1/panels",
            params={
                "search": _api_search_text(model),
                "market": "GLOBAL",
                "perPage": 100,
                "page": 1,
            },
        )
        rows = listing.get("data") if isinstance(listing, dict) else None
        if not isinstance(rows, list):
            raise ProviderError("Solar Stack API returned an invalid panel search response")

        exact_rows = [
            row
            for row in rows
            if isinstance(row, dict)
            and isinstance(row.get("name"), str)
            and normalize_component_model(row["name"]) == normalized
            and isinstance(row.get("id"), str)
            and row["id"].strip()
        ]
        if len(exact_rows) != 1:
            # Zero means no exact model. More than one means the model alone
            # cannot safely distinguish manufacturer or edition.
            return None

        candidate = exact_rows[0]
        detail = self._get_json(f"/v1/panels/{candidate['id']}")
        payload = detail.get("data") if isinstance(detail, dict) else None
        if not isinstance(payload, dict):
            raise ProviderError("Solar Stack API returned an invalid panel record")
        if (
            not isinstance(payload.get("name"), str)
            or normalize_component_model(payload["name"]) != normalized
            or payload.get("manufacturer") != candidate.get("manufacturer")
        ):
            raise ProviderError("Solar Stack API exact-model identity did not match")

        return self._to_profile(payload)

    def _get_json(
        self,
        path: str,
        *,
        params: dict[str, str | int] | None = None,
    ) -> dict[str, object]:
        try:
            with httpx.Client(
                timeout=self._timeout_seconds,
                transport=self._transport,
                follow_redirects=False,
            ) as client:
                response = client.get(
                    f"{_BASE_URL}{path}",
                    params=params,
                    headers={
                        "Accept": "application/json",
                        "Authorization": f"Bearer {self._api_key}",
                    },
                )
                response.raise_for_status()
                if len(response.content) > _MAX_RESPONSE_BYTES:
                    raise ProviderError("Solar Stack API response exceeded the size limit")
                payload = response.json()
        except ProviderError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            # Do not propagate request/response text: it can contain credentials
            # or upstream details that should not reach user-facing traces.
            raise ProviderError("Solar Stack Partner API request failed") from exc
        if not isinstance(payload, dict):
            raise ProviderError("Solar Stack API returned an invalid JSON response")
        return payload

    @staticmethod
    def _to_profile(payload: dict[str, object]) -> ComponentProfile:
        model = payload.get("name")
        manufacturer = payload.get("manufacturer")
        if not isinstance(model, str) or not model.strip():
            raise ProviderError("Solar Stack API record has no exact model")
        if not isinstance(manufacturer, str) or not manufacturer.strip():
            raise ProviderError("Solar Stack API record has no manufacturer")

        series = payload.get("series")
        series = series if isinstance(series, dict) else {}
        api_model_url = _https_url(payload.get("url"))
        if api_model_url is None:
            raise ProviderError("Solar Stack API record has no safe model page")

        datasheet_urls = []
        raw_datasheets = payload.get("datasheets")
        if isinstance(raw_datasheets, list):
            for item in raw_datasheets:
                if not isinstance(item, dict) or item.get("type") != "datasheet":
                    continue
                datasheet_url = _https_url(item.get("url"))
                if datasheet_url and datasheet_url not in datasheet_urls:
                    datasheet_urls.append(datasheet_url)
        # When the response exposes more than one edition, do not guess which
        # PDF belongs to the submitted asset; the Solar Stack model page remains
        # the auditable entry point until a reviewer confirms the correct sheet.
        parameter_source = datasheet_urls[0] if len(datasheet_urls) == 1 else api_model_url
        parameter_sources: dict[str, str] = {}
        values = {
            "rated_power_w": _number(payload.get("pmax")),
            "hail_resistance_mm": _number(series.get("hailDiameterMm")),
            "hail_impact_velocity_m_s": _number(series.get("hailSpeedMs")),
            "front_static_load_pa": _number(series.get("maxLoadFrontPa")),
            "back_static_load_pa": _number(series.get("maxLoadRearPa")),
        }
        for field, value in values.items():
            if value is not None:
                parameter_sources[field] = parameter_source

        markets = series.get("markets")
        global_market = isinstance(markets, list) and any(
            isinstance(market, str) and market.upper() == "GLOBAL" for market in markets
        )
        notes = [
            "来源为 Solar Stack Partner API；数据库规格转录自厂家资料，仍需核对该项目实际型号、资料版本与安装配置。",
            "仅接受完整型号精确匹配且市场筛选为 GLOBAL 的唯一记录；未命中或存在多个同名记录时不自动择一。",
            "API 空字段表示尚未收录，系统保留未知，不推定设备没有该能力。",
            "Solar Stack 当前提供的正面/背面最大静态载荷不等同项目设计风压或屋面结构雪荷载；不作工程换算。",
        ]
        if len(datasheet_urls) > 1:
            notes.append(
                "该型号返回多个 Datasheet 版本；系统未猜测版本，参数来源链接到 Solar Stack 型号页，需人工核对适用版本。"
            )
        elif not datasheet_urls:
            notes.append("API 未返回 Datasheet PDF 链接；请从型号页核对厂家原始资料。")
        manufacturer_page = _https_url(series.get("sourceUrl"))
        if manufacturer_page is None:
            notes.append("API 未提供厂商产品页链接。")

        return ComponentProfile(
            component_model=model.strip(),
            manufacturer=manufacturer.strip(),
            rated_power_w=values["rated_power_w"],
            hail_resistance_mm=values["hail_resistance_mm"],
            hail_impact_velocity_m_s=values["hail_impact_velocity_m_s"],
            front_static_load_pa=values["front_static_load_pa"],
            back_static_load_pa=values["back_static_load_pa"],
            # Solar Stack does not currently publish fields with these exact
            # meanings. Do not infer them from the two static-load directions.
            wind_load_pa=None,
            snow_load_pa=None,
            market_version="GLOBAL" if global_market else "GLOBAL market query; series market unreported",
            model_derivation_method="exact_model_partner_api_lookup",
            source_document_type="Solar Stack Partner API; manufacturer datasheet link",
            source_note=(
                "Solar Stack is a third-party read-only catalogue. Imported values are traceable to its model record and, "
                "when a single datasheet is returned, the linked PDF. Installation applicability has not been established."
            ),
            source_url=api_model_url,
            source_name="Solar Stack Partner API",
            retrieved_at=datetime.now(UTC),
            match_confidence=1.0,
            parameter_sources=parameter_sources,
            lookup_notes=notes,
        )
