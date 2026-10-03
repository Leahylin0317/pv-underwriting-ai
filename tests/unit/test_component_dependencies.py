import json
from pathlib import Path

import pytest
from app.api.component_dependencies import (
    get_component_catalog_path,
    get_component_provider,
)
from app.providers.component import LocalFirstComponentProvider
from fastapi import HTTPException


def catalog_payload(
    component_model: str,
) -> list[dict[str, object]]:
    return [
        {
            "component_model": (
                component_model
            ),
            "manufacturer": "测试组件厂商",
            "rated_power_w": 600,
            "hail_resistance_mm": 25,
            "wind_load_pa": 2400,
            "snow_load_pa": 5400,
            "source_url": None,
            "source_name": "测试组件目录",
            "retrieved_at": (
                "2026-09-26T00:00:00+08:00"
            ),
            "match_confidence": 1.0,
        }
    ]


def test_uses_default_imported_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "PV_COMPONENT_CATALOG_PATH",
        "",
    )

    path = get_component_catalog_path()
    provider = get_component_provider()

    assert path.name == (
        "component_catalog_2026-10-01.json"
    )
    assert provider.lookup(
        "JAM66D42-580/MB"
    ) is not None
    imported = provider.lookup("LR5-54HTB-440M")
    assert imported is not None
    assert imported.hail_resistance_mm == 25
    assert imported.front_static_load_pa == 5400
    assert imported.wind_load_pa is None
    assert imported.snow_load_pa is None
    assert provider.lookup("CS6.2-66HB-610H") is None

    exact_ja = provider.lookup("JAM72D42-630/LB")
    listed_ja = provider.lookup("JAM72D42-630W")
    assert exact_ja is not None
    assert listed_ja is not None
    assert exact_ja.component_model != listed_ja.component_model
    assert exact_ja.front_static_load_pa == 5400
    assert exact_ja.wind_load_pa is None


def test_loads_configured_component_catalog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog_path = (
        tmp_path / "component-catalog.json"
    )
    catalog_path.write_text(
        json.dumps(
            catalog_payload(
                "CUSTOM-MODULE-600W"
            ),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv(
        "PV_COMPONENT_CATALOG_PATH",
        str(catalog_path),
    )

    provider = get_component_provider()

    profile = provider.lookup(
        "CUSTOM-MODULE-600W"
    )

    assert profile is not None
    assert profile.rated_power_w == 600
    assert profile.source_name == (
        "测试组件目录"
    )


def test_reports_unavailable_catalog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing_path = (
        tmp_path / "missing.json"
    )

    monkeypatch.setenv(
        "PV_COMPONENT_CATALOG_PATH",
        str(missing_path),
    )

    with pytest.raises(
        HTTPException,
    ) as exc_info:
        get_component_provider()

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == (
        "Component catalog is unavailable"
    )


def test_configured_online_catalog_is_connected_to_underwriting_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PV_COMPONENT_CATALOG_PATH", "")
    monkeypatch.setenv(
        "PV_COMPONENT_ONLINE_CATALOG_URL",
        "https://catalog.example.test/components",
    )
    monkeypatch.setenv("PV_COMPONENT_APPROVED_SOURCE_DOMAINS", "jasolar.com")

    provider = get_component_provider()

    assert isinstance(provider, LocalFirstComponentProvider)
    assert provider.local.lookup("JAM66D42-580/MB") is not None
