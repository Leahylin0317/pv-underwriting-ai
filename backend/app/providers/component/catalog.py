import json
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


def normalize_component_model(
    component_model: str,
) -> str:
    """生成用于精确目录匹配的型号键。"""

    return "".join(
        character.casefold()
        for character in component_model.strip()
        if character.isalnum()
    )


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
            normalized_model = (
                normalize_component_model(
                    profile.component_model
                )
            )

            if not normalized_model:
                raise ValueError(
                    "component model must contain "
                    "letters or numbers"
                )

            if normalized_model in catalog:
                raise ValueError(
                    "duplicate normalized component "
                    f"model: {normalized_model}"
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

        if not normalized_model:
            return None

        profile = self._catalog.get(
            normalized_model
        )

        if profile is None:
            return None

        return profile.model_copy(deep=True)
