from abc import ABC, abstractmethod

from app.contracts import OcrField

from ..common import MaterialInput


class OcrProvider(ABC):
    """所有OCR服务必须实现的统一接口。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """返回Provider名称。"""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """返回模型名称或版本。"""

    @abstractmethod
    def extract(self, material_input: MaterialInput) -> list[OcrField]:
        """从一份材料中提取结构化文字字段。"""