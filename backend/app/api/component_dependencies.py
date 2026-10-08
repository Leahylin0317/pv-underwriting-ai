import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException, status

from app.providers import ProviderError
from app.providers.component import (
    CatalogComponentProvider,
    ComponentCatalogOverlayProvider,
    ComponentProvider,
    LocalFirstComponentProvider,
    RemoteCatalogComponentProvider,
    SolarStackPartnerApiComponentProvider,
)

PROJECT_ROOT = (
    Path(__file__).resolve().parents[3]
)

DEFAULT_COMPONENT_CATALOG_PATH = (
    PROJECT_ROOT
    / "data"
    / "catalogs"
    / "component_catalog_2026-10-01.json"
)


def get_component_catalog_path() -> Path:
    """读取组件目录路径配置。"""

    load_dotenv(
        dotenv_path=PROJECT_ROOT / ".env",
        override=False,
    )

    configured_path = os.getenv(
        "PV_COMPONENT_CATALOG_PATH",
        "",
    ).strip()

    if not configured_path:
        return (
            DEFAULT_COMPONENT_CATALOG_PATH
        )

    path = Path(
        configured_path
    ).expanduser()

    if not path.is_absolute():
        path = PROJECT_ROOT / path

    return path


def get_component_provider() -> ComponentProvider:
    """Create local-first lookup with optional verified online fallback."""

    catalog_path = (
        get_component_catalog_path()
    )

    try:
        local = CatalogComponentProvider.from_json_file(catalog_path)
    except ProviderError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Component catalog is unavailable"
            ),
        ) from exc

    correction_path = Path(
        os.getenv(
            "PV_COMPONENT_CORRECTIONS_PATH",
            "outputs/component-corrections.json",
        ).strip()
        or "outputs/component-corrections.json"
    ).expanduser()
    if not correction_path.is_absolute():
        correction_path = PROJECT_ROOT / correction_path
    if correction_path.exists():
        try:
            corrections = CatalogComponentProvider.from_json_file(correction_path)
        except ProviderError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Component correction catalog is invalid",
            ) from exc
        local = ComponentCatalogOverlayProvider(local, corrections)

    provider: ComponentProvider = local

    solar_stack_key = os.getenv("PV_SOLAR_STACK_API_KEY", "").strip()
    if solar_stack_key:
        provider = LocalFirstComponentProvider(
            provider,
            SolarStackPartnerApiComponentProvider(solar_stack_key),
        )

    online_url = os.getenv("PV_COMPONENT_ONLINE_CATALOG_URL", "").strip()
    if not online_url:
        return provider
    domains = tuple(
        part.strip()
        for part in os.getenv(
            "PV_COMPONENT_APPROVED_SOURCE_DOMAINS", "jasolar.com"
        ).split(",")
        if part.strip()
    )
    try:
        online = RemoteCatalogComponentProvider(
            online_url,
            approved_source_domains=domains,
            api_key=os.getenv("PV_COMPONENT_ONLINE_CATALOG_API_KEY", "").strip(),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Online component catalog configuration is invalid",
        ) from exc
    return LocalFirstComponentProvider(provider, online)
