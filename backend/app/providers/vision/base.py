from abc import ABC, abstractmethod

from pydantic import BaseModel

from app.contracts import Bbox, RiskFinding

from ..common import MaterialInput


class VisionAnalysis(BaseModel):
    findings: list[RiskFinding]
    watermark_present: bool | None = None
    watermark_bbox: Bbox | None = None
    watermark_evidence: str | None = None


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

    def analyze_with_watermark(self, material_input: MaterialInput) -> VisionAnalysis:
        """同时返回风险点和全景照水印判断。"""
        return VisionAnalysis(findings=self.analyze(material_input))
