import json
from pathlib import Path

import pytest
from app.providers import ProviderError
from app.providers.component import (
    CatalogComponentProvider,
)


def test_loads_component_catalog_file(
    tmp_path: Path,
) -> None:
    catalog_path = (
        tmp_path / "component-catalog.json"
    )

    catalog_path.write_text(
        json.dumps(
            [
                {
                    "component_model": (
                        "PV-MODULE-580W"
                    ),
                    "manufacturer": (
                        "示例组件厂商"
                    ),
                    "rated_power_w": 580,
                    "hail_resistance_mm": 25,
                    "wind_load_pa": 2400,
                    "snow_load_pa": 5400,
                    "source_url": None,
                    "source_name": (
                        "测试组件目录"
                    ),
                    "retrieved_at": (
                        "2026-09-26T00:00:00"
                        "+08:00"
                    ),
                    "match_confidence": 1.0,
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    provider = (
        CatalogComponentProvider
        .from_json_file(catalog_path)
    )

    profile = provider.lookup(
        "pv module 580w"
    )

    assert profile is not None
    assert profile.component_model == (
        "PV-MODULE-580W"
    )
    assert profile.rated_power_w == 580
    assert profile.source_name == (
        "测试组件目录"
    )


def test_rejects_invalid_catalog_json(
    tmp_path: Path,
) -> None:
    catalog_path = (
        tmp_path / "invalid.json"
    )
    catalog_path.write_text(
        "{not-valid-json",
        encoding="utf-8",
    )

    with pytest.raises(
        ProviderError,
        match="component catalog is invalid",
    ):
        (
            CatalogComponentProvider
            .from_json_file(catalog_path)
        )


def test_rejects_invalid_catalog_schema(
    tmp_path: Path,
) -> None:
    catalog_path = (
        tmp_path / "invalid-schema.json"
    )
    catalog_path.write_text(
        json.dumps(
            [
                {
                    "component_model": (
                        "PV-MODULE-580W"
                    ),
                    "rated_power_w": -1,
                }
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ProviderError,
        match="component catalog is invalid",
    ):
        (
            CatalogComponentProvider
            .from_json_file(catalog_path)
        )
