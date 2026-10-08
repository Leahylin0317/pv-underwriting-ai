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
        "pv-module-580w"
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


def test_official_component_catalog_keeps_load_direction_and_provenance() -> None:
    project_root = Path(__file__).resolve().parents[2]
    catalog_path = project_root / "data/catalogs/component_catalog_2026-10-01.json"
    reference_path = project_root / "data/reference/component_parameters_2026-10-01.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    eligible = [record for record in reference["records"] if record["auto_match_eligible"]]
    imported = [profile for profile in catalog if ", row " in profile["source_name"]]

    assert len(eligible) == 69
    assert len(imported) == len(eligible)
    assert all(profile.get("front_static_load_pa") for profile in imported)
    assert all(profile.get("back_static_load_pa") for profile in imported)
    assert all("front_static_load_pa" in profile["parameter_sources"] for profile in imported)
    assert all("back_static_load_pa" in profile["parameter_sources"] for profile in imported)
    assert all(profile.get("wind_load_pa") is None for profile in imported)
    assert all(profile.get("snow_load_pa") is None for profile in imported)


def test_incomplete_model_returns_human_review_variant_without_auto_matching() -> None:
    project_root = Path(__file__).resolve().parents[2]
    catalog_path = project_root / "data/catalogs/component_catalog_2026-10-01.json"
    provider = CatalogComponentProvider.from_json_file(catalog_path)

    assert provider.lookup("JAM72D42-630W") is None
    candidates = provider.find_variant_candidates("JAM72D42-630W")

    assert [candidate.component_model for candidate in candidates] == [
        "JAM72D42-630/LB"
    ]
    assert candidates[0].rated_power_w == 630
    assert candidates[0].front_static_load_pa == 5400
    assert candidates[0].back_static_load_pa == 2400
    assert candidates[0].hail_resistance_mm is None
    exact = provider.lookup("JAM72D42-630/LB")
    assert exact is not None
    assert exact.component_model == "JAM72D42-630/LB"
