from datetime import UTC, datetime

import pytest
from app.contracts import ComponentProfile
from app.providers.component import (
    CatalogComponentProvider,
    normalize_component_model,
)


def component_profile(
    component_model: str = "PV-MODULE-580W",
) -> ComponentProfile:
    return ComponentProfile(
        component_model=component_model,
        manufacturer="示例组件厂商",
        rated_power_w=580,
        hail_resistance_mm=25,
        wind_load_pa=2400,
        snow_load_pa=5400,
        source_url=(
            "https://example.com/component.pdf"
        ),
        source_name="本地可信组件目录",
        retrieved_at=datetime(
            2026,
            9,
            26,
            9,
            0,
            tzinfo=UTC,
        ),
        match_confidence=1.0,
    )


def test_normalizes_component_model() -> None:
    assert normalize_component_model(
        " PV-Module 580W "
    ) == "pvmodule580w"


def test_finds_exact_component_model() -> None:
    original = component_profile()

    provider = CatalogComponentProvider(
        profiles=[original]
    )

    result = provider.lookup(
        "PV-MODULE-580W"
    )

    assert result is not None
    assert result.component_model == (
        "PV-MODULE-580W"
    )
    assert result.rated_power_w == 580
    assert result.wind_load_pa == 2400
    assert result.match_confidence == 1.0
    assert result is not original
    assert provider.name == (
        "local-component-catalog"
    )


def test_matches_case_and_separator_variants() -> None:
    provider = CatalogComponentProvider(
        profiles=[component_profile()]
    )

    result = provider.lookup(
        "pv module_580w"
    )

    assert result is not None
    assert result.component_model == (
        "PV-MODULE-580W"
    )


def test_returns_none_for_unknown_or_empty_model() -> None:
    provider = CatalogComponentProvider(
        profiles=[component_profile()]
    )

    assert provider.lookup(
        "UNKNOWN-MODEL"
    ) is None
    assert provider.lookup("   ") is None


def test_rejects_duplicate_normalized_models() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "duplicate normalized component model"
        ),
    ):
        CatalogComponentProvider(
            profiles=[
                component_profile(
                    "PV-MODULE-580W"
                ),
                component_profile(
                    "pv module 580w"
                ),
            ]
        )
