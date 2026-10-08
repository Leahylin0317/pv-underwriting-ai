"""Verified online component catalog and local-first lookup."""

from urllib.parse import urlparse

import httpx
from pydantic import ValidationError

from app.contracts import ComponentProfile
from app.providers.common import ProviderError

from .base import ComponentProvider
from .catalog import normalize_component_model

_PARAMETERS = (
    "rated_power_w",
    "front_static_load_pa",
    "back_static_load_pa",
    "hail_resistance_mm",
    "hail_impact_velocity_m_s",
    "wind_load_pa",
    "snow_load_pa",
)


def _approved_https(url: str, domains: tuple[str, ...]) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and not parsed.username and not parsed.password and any(
        host == domain or host.endswith("." + domain) for domain in domains
    )


class RemoteCatalogComponentProvider(ComponentProvider):
    """Query a configured, reviewed catalog; search snippets are never specifications.

    The endpoint must return ``{"verified": true, "profile": ComponentProfile}``.
    A 404 means no exact, approved record exists.
    """

    def __init__(
        self,
        url: str,
        *,
        approved_source_domains: tuple[str, ...],
        api_key: str = "",
        timeout_seconds: float = 15.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("component catalog URL must be HTTPS")
        if timeout_seconds <= 0:
            raise ValueError("component catalog timeout must be positive")
        domains = tuple(domain.strip().lower() for domain in approved_source_domains)
        if not domains or any(
            not domain
            or any(
                not label or not all(character.isalnum() or character == "-" for character in label)
                for label in domain.split(".")
            )
            for domain in domains
        ):
            raise ValueError("approved source domains are invalid")
        self.url = url
        self.domains = domains
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    @property
    def name(self) -> str:
        return "verified-online-component-catalog"

    def lookup(self, component_model: str) -> ComponentProfile | None:
        normalized = normalize_component_model(component_model)
        if not normalized:
            return None
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            with httpx.Client(
                timeout=self.timeout_seconds,
                transport=self.transport,
                follow_redirects=False,
            ) as client:
                response = client.get(
                    self.url,
                    params={"model": component_model},
                    headers=headers,
                )
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                if len(response.content) > 1_000_000:
                    raise ValueError("component catalog response is too large")
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError("online component catalog request failed") from exc

        try:
            if not isinstance(payload, dict) or payload.get("verified") is not True:
                raise ValueError("record has not been verified")
            profile = ComponentProfile.model_validate(payload["profile"])
            if normalize_component_model(profile.component_model) != normalized:
                raise ValueError("online record does not match the exact model")
            if not profile.source_url or not _approved_https(
                profile.source_url, self.domains
            ):
                raise ValueError("record has no approved manufacturer source")
            if not profile.manufacturer:
                raise ValueError("record has no manufacturer")
            if any(
                not _approved_https(profile.parameter_sources.get(field, ""), self.domains)
                for field in _PARAMETERS
                if getattr(profile, field) is not None
            ):
                raise ValueError("record has no approved source for every parameter")
            return profile
        except (KeyError, ValueError, ValidationError) as exc:
            raise ProviderError("online component catalog returned unverified data") from exc


class LocalFirstComponentProvider(ComponentProvider):
    """Use local values first and fill only missing values from a verified API."""

    def __init__(
        self,
        local: ComponentProvider,
        online: ComponentProvider,
    ) -> None:
        self.local = local
        self.online = online

    @property
    def name(self) -> str:
        return "local-first-component-catalog"

    def lookup(self, component_model: str) -> ComponentProfile | None:
        local = self.local.lookup(component_model)
        if local is not None and all(
            getattr(local, field) is not None for field in _PARAMETERS
        ):
            return local

        try:
            online = self.online.lookup(component_model)
        except ProviderError:
            if local is not None:
                return local.model_copy(
                    update={
                        "lookup_notes": [
                            *local.lookup_notes,
                            "在线组件目录查询失败，缺失参数未补齐",
                        ]
                    }
                )
            raise
        if online is None:
            return local
        if local is None:
            return online

        update = {
            field: getattr(online, field)
            for field in _PARAMETERS
            if getattr(local, field) is None and getattr(online, field) is not None
        }
        if not update:
            return local
        update["parameter_sources"] = {
            **local.parameter_sources,
            **{
                field: local.source_url or local.source_name
                for field in _PARAMETERS
                if getattr(local, field) is not None
                and field not in local.parameter_sources
            },
            **{
                field: online.parameter_sources[field]
                for field in update
                if field in online.parameter_sources
            },
        }
        update["source_name"] = f"{local.source_name}; {online.source_name}"
        update["source_url"] = online.source_url
        update["retrieved_at"] = online.retrieved_at
        update["match_confidence"] = min(
            local.match_confidence, online.match_confidence
        )
        return local.model_copy(update=update)


class ComponentCatalogOverlayProvider(ComponentProvider):
    """Fill only missing local values with operator-confirmed corrections."""

    def __init__(self, base: ComponentProvider, corrections: ComponentProvider) -> None:
        self.base = base
        self.corrections = corrections

    @property
    def name(self) -> str:
        return "local-catalog-with-reviewed-corrections"

    def lookup(self, component_model: str) -> ComponentProfile | None:
        base = self.base.lookup(component_model)
        correction = self.corrections.lookup(component_model)
        if correction is None:
            return base
        if base is None:
            return correction

        value_fields = (
            "rated_power_w",
            "hail_resistance_mm",
            "wind_load_pa",
            "snow_load_pa",
            "front_static_load_pa",
            "back_static_load_pa",
            "hail_impact_velocity_m_s",
        )
        updates = {
            field: getattr(correction, field)
            for field in value_fields
            if getattr(base, field) is None and getattr(correction, field) is not None
        }
        if not updates:
            return base
        updates["parameter_sources"] = {
            **base.parameter_sources,
            **{
                field: correction.parameter_sources[field]
                for field in updates
                if field in correction.parameter_sources
            },
        }
        updates["source_name"] = f"{base.source_name}; {correction.source_name}"
        updates["lookup_notes"] = [
            *base.lookup_notes,
            *correction.lookup_notes,
            "人工补正仅填充原目录缺失字段；已有目录数值不会被覆盖。",
        ]
        return base.model_copy(update=updates)
