from app.contracts import ComponentProfile

from .base import ComponentProvider


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
