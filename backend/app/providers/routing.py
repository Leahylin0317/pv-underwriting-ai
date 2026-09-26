from app.contracts import (
    MaterialCategory,
    OcrField,
    RiskFinding,
)

from .common import MaterialInput
from .ocr.base import OcrProvider
from .vision.base import VisionProvider

OCR_MEDIA_TYPES = frozenset(
    {
        "application/pdf",
        "image/jpeg",
        "image/png",
    }
)

VISION_MEDIA_TYPES = frozenset(
    {
        "image/jpeg",
        "image/png",
    }
)

OCR_MATERIAL_CATEGORIES = frozenset(
    {
        MaterialCategory.FILING_CERTIFICATE,
        MaterialCategory.GRID_CONNECTION_DOCUMENT,
        MaterialCategory.ELECTRICAL_GROUNDING,
        MaterialCategory.COMPONENT_NAMEPLATE,
        MaterialCategory.INVERTER_NAMEPLATE,
        MaterialCategory.COMBINER_BOX,
        MaterialCategory.MONITORING_OPTIONAL,
        MaterialCategory.OTHER,
    }
)

VISION_MATERIAL_CATEGORIES = frozenset(
    {
        MaterialCategory.PANORAMA,
        MaterialCategory.ROOF_CONNECTION,
        MaterialCategory.PARAPET,
        MaterialCategory.WORKSHOP,
        MaterialCategory.ELECTRICAL_GROUNDING,
        MaterialCategory.COMBINER_BOX,
        MaterialCategory.MONITORING_OPTIONAL,
        MaterialCategory.OTHER,
    }
)


def should_run_ocr(
    material_input: MaterialInput,
) -> bool:
    """判断当前材料是否需要调用 OCR。"""

    material = material_input.material

    return (
        material.media_type in OCR_MEDIA_TYPES
        and material.category
        in OCR_MATERIAL_CATEGORIES
    )


def should_run_vision(
    material_input: MaterialInput,
) -> bool:
    """判断当前材料是否需要调用视觉风险识别。"""

    material = material_input.material

    return (
        material.media_type in VISION_MEDIA_TYPES
        and material.category
        in VISION_MATERIAL_CATEGORIES
    )


class RoutedOcrProvider(OcrProvider):
    """仅把适合 OCR 的材料交给下游 Provider。"""

    def __init__(
        self,
        delegate: OcrProvider,
    ) -> None:
        self._delegate = delegate

    @property
    def name(self) -> str:
        return self._delegate.name

    @property
    def model_name(self) -> str:
        return self._delegate.model_name

    def extract(
        self,
        material_input: MaterialInput,
    ) -> list[OcrField]:
        if not should_run_ocr(material_input):
            return []

        return self._delegate.extract(
            material_input
        )


class RoutedVisionProvider(VisionProvider):
    """仅把适合风险识别的图片交给下游 Provider。"""

    def __init__(
        self,
        delegate: VisionProvider,
    ) -> None:
        self._delegate = delegate

    @property
    def name(self) -> str:
        return self._delegate.name

    @property
    def model_name(self) -> str:
        return self._delegate.model_name

    def analyze(
        self,
        material_input: MaterialInput,
    ) -> list[RiskFinding]:
        if not should_run_vision(material_input):
            return []

        return self._delegate.analyze(
            material_input
        )
