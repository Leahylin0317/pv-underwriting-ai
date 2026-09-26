import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException, status

from app.providers import ProviderError
from app.providers.component import (
    CatalogComponentProvider,
    ComponentProvider,
)

PROJECT_ROOT = (
    Path(__file__).resolve().parents[3]
)

DEFAULT_COMPONENT_CATALOG_PATH = (
    PROJECT_ROOT
    / "data"
    / "examples"
    / "component_catalog.sample.json"
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
    """创建组件目录 Provider。"""

    catalog_path = (
        get_component_catalog_path()
    )

    try:
        return (
            CatalogComponentProvider
            .from_json_file(catalog_path)
        )
    except ProviderError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Component catalog is unavailable"
            ),
        ) from exc
