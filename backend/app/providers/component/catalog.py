import json
import re
import unicodedata
from pathlib import Path

from pydantic import (
    TypeAdapter,
    ValidationError,
)

from app.contracts import ComponentProfile

from ..common import ProviderError
from .base import ComponentProvider

_COMPONENT_PROFILE_LIST_ADAPTER = (
    TypeAdapter(
        list[ComponentProfile]
    )
)
MIN_AUTOMATIC_MODEL_MATCH_CONFIDENCE = 0.8


def normalize_component_model(
    component_model: str,
) -> str:
    """Normalize typography while preserving manufacturer-significant punctuation.

    Case, full-width forms, dash glyphs, and whitespace are presentation details.
    Slashes, hyphens, dots, plus signs, and underscores can encode a model suffix
    or product variant, so they remain part of the lookup key.
    """

    normalized = unicodedata.normalize("NFKC", component_model).casefold().strip()
    for dash in "‐‑‒–—―−﹘﹣－":
        normalized = normalized.replace(dash, "-")
    return "".join(character for character in normalized if not character.isspace())


class CatalogComponentProvider(
    ComponentProvider
):
    """使用本地可信组件目录查询规格参数。"""

    def __init__(
        self,
        profiles: list[ComponentProfile],
    ) -> None:
        catalog: dict[
            str,
            ComponentProfile,
        ] = {}

        for profile in profiles:
            for model in (profile.component_model, *profile.model_aliases):
                normalized_model = normalize_component_model(model)
                if not any(character.isalnum() for character in normalized_model):
                    raise ValueError("component model must contain letters or numbers")
                if normalized_model in catalog:
                    raise ValueError(
                        f"duplicate normalized component model: {normalized_model}"
                    )
                catalog[normalized_model] = profile

        self._catalog = catalog

    @classmethod
    def from_json_file(
        cls,
        path: str | Path,
    ) -> "CatalogComponentProvider":
        """从 UTF-8 JSON 文件加载组件目录。"""

        catalog_path = Path(path)

        try:
            raw_text = catalog_path.read_text(
                encoding="utf-8-sig"
            )
        except (
            OSError,
            UnicodeError,
        ) as exc:
            raise ProviderError(
                "component catalog could not be read"
            ) from exc

        try:
            raw_payload = json.loads(raw_text)

            profiles = (
                _COMPONENT_PROFILE_LIST_ADAPTER
                .validate_python(raw_payload)
            )
        except (
            json.JSONDecodeError,
            ValidationError,
        ) as exc:
            raise ProviderError(
                "component catalog is invalid"
            ) from exc

        try:
            return cls(profiles=profiles)
        except ValueError as exc:
            raise ProviderError(
                "component catalog is invalid"
            ) from exc

    @property
    def name(self) -> str:
        return "local-component-catalog"

    def lookup(
        self,
        component_model: str,
    ) -> ComponentProfile | None:
        normalized_model = (
            normalize_component_model(
                component_model
            )
        )

        if not any(character.isalnum() for character in normalized_model):
            return None

        profile = self._catalog.get(
            normalized_model
        )

        if (
            profile is None
            or profile.match_confidence < MIN_AUTOMATIC_MODEL_MATCH_CONFIDENCE
        ):
            return None

        return profile.model_copy(deep=True)

    def find_variant_candidates(
        self,
        component_model: str,
        *,
        limit: int = 8,
    ) -> list[ComponentProfile]:
        """Return near-exact catalogue variants for human identity review only.

        A trailing watt unit and a slash-delimited variant suffix can be absent
        from equipment inventories even though they are significant on the
        nameplate. These candidates must never be used by ``lookup``.
        """
        if limit <= 0:
            return []
        requested = normalize_component_model(component_model)
        requested_key = _variant_search_key(requested)
        if len(requested_key) < 7:
            return []

        matches: dict[str, ComponentProfile] = {}
        for profile in self._catalog.values():
            exact = normalize_component_model(profile.component_model)
            if exact == requested:
                continue
            if profile.match_confidence < MIN_AUTOMATIC_MODEL_MATCH_CONFIDENCE:
                continue
            candidate_key = _variant_search_key(exact)
            if not candidate_key.startswith(requested_key):
                continue
            matches[exact] = profile

        ordered = sorted(
            matches.values(),
            key=lambda item: (
                _variant_search_key(item.component_model) != requested_key,
                -item.match_confidence,
                item.component_model.casefold(),
            ),
        )
        return [item.model_copy(deep=True) for item in ordered[:limit]]


def _variant_search_key(normalized_model: str) -> str:
    """Remove only a trailing watt unit and slash suffix for candidate search."""
    without_watt = re.sub(r"(?<=\d)w$", "", normalized_model)
    return without_watt.split("/", maxsplit=1)[0]
