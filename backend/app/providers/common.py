from dataclasses import dataclass

from app.contracts import Material


@dataclass(frozen=True, slots=True)
class MaterialInput:
    """传递给OCR和视觉Provider的材料内容。"""

    material: Material
    content: bytes