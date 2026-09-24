from abc import ABC, abstractmethod

from app.contracts import RiskFinding

from ..common import MaterialInput


class VisionProvider(ABC):
    """所有视觉识别服务必须实现的统一接口。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """返回Provider名称。"""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """返回模型名称或版本。"""

    @abstractmethod
    def analyze(self, material_input: MaterialInput) -> list[RiskFinding]:
        """分析一份图片材料并返回风险点。"""