import base64
import json
from typing import Any

import httpx
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)

from app.contracts import (
    Bbox,
    DetectionStatus,
    RiskCategory,
    RiskFinding,
    RiskSeverity,
)
from app.settings import VlmSettings

from ..common import MaterialInput, ProviderError
from .base import VisionProvider

SUPPORTED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
}

DEFAULT_CONFIDENCE_THRESHOLD = 0.65

RISK_CATEGORY_VALUES = "、".join(
    category.value
    for category in RiskCategory
)

SYSTEM_PROMPT = f"""你是分布式光伏财产险的图片风险识别模块。
只根据图片中能够直接观察到的证据进行判断，不得猜测或补充图片外的信息。
必须返回一个合法的 JSON 对象，顶层字段固定为 findings。
findings 必须是数组。

每个风险点只能包含以下字段：
category、label、detection_status、severity、confidence、bbox、
evidence_text、requires_manual_review。

category 只能是以下风险类别之一：
{RISK_CATEGORY_VALUES}。

风险类别边界：
- minor_shading：组件表面存在面积较小的阴影或轻微实物遮挡。
- severe_shading：组件存在明显的大面积、持续性遮挡。
- flammable_material：组件或电气设备附近可见纸箱、木材、干草、
  包装物等明确的可燃物堆积。
- 屋瓦、苔藓、污渍、远处植被不能直接判定为 flammable_material。
- hazardous_material：必须能看到危险化学品、气瓶、油品容器或明确标识。
- mountain_environment：项目现场本身位于山地，远处背景山体不算。
- missing_parapet_or_guardrail：仅适用于平屋顶、检修平台或通道，
  不能因为斜屋顶没有护栏就直接判定风险。
- 无法确定风险类别时返回 uncertain，并要求人工复核。
- 不允许把图片中没有出现的风险写入 findings。

detection_status 只能是 detected 或 uncertain。
severity 只能是 info、low、medium、high、critical、unknown。
confidence 必须是 0 到 1 之间的小数。
requires_manual_review 必须是 true 或 false。

bbox 无法可靠定位时必须返回 null。
bbox 能够可靠定位时必须是 JSON 对象，并且必须包含：
x_min、y_min、x_max、y_max、coordinate_space。
坐标必须是 0 到 1 之间的归一化小数。
coordinate_space 必须固定为 normalized_0_1。

如果没有发现风险，返回：
{{"findings": []}}

不要输出未发现的风险。
不要返回 Markdown。
不要返回代码块。
不要返回 JSON 以外的说明。
"""


class VisionFindingPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: RiskCategory
    label: str = Field(min_length=1)
    detection_status: DetectionStatus
    severity: RiskSeverity
    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )
    bbox: Bbox | None = None
    evidence_text: str = Field(min_length=1)
    requires_manual_review: bool

    @model_validator(mode="before")
    @classmethod
    def add_default_coordinate_space(
        cls,
        value: Any,
    ) -> Any:
        if not isinstance(value, dict):
            return value

        bbox = value.get("bbox")

        if (
            not isinstance(bbox, dict)
            or "coordinate_space" in bbox
        ):
            return value

        return {
            **value,
            "bbox": {
                **bbox,
                "coordinate_space": "normalized_0_1",
            },
        }


class VisionResponsePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[VisionFindingPayload]


class CompatibleVisionProvider(VisionProvider):
    """调用 OpenAI Chat Completions 兼容接口的视觉识别 Provider。"""

    def __init__(
        self,
        settings: VlmSettings,
        *,
        transport: httpx.BaseTransport | None = None,
        confidence_threshold: float = (
            DEFAULT_CONFIDENCE_THRESHOLD
        ),
    ) -> None:
        if not 0.0 <= confidence_threshold <= 1.0:
            raise ValueError(
                "confidence_threshold must be "
                "between zero and one"
            )

        self._settings = settings
        self._transport = transport
        self._confidence_threshold = (
            confidence_threshold
        )

    @property
    def name(self) -> str:
        return "openai-compatible-vision"

    @property
    def model_name(self) -> str:
        return self._settings.model

    def analyze(
        self,
        material_input: MaterialInput,
    ) -> list[RiskFinding]:
        material = material_input.material

        if material.media_type not in SUPPORTED_IMAGE_TYPES:
            return []

        if not material_input.content:
            raise ProviderError(
                "vision provider received an empty image"
            )

        response_payload = self._request_model(
            material_input
        )

        return self._to_risk_findings(
            material_id=material.material_id,
            response_payload=response_payload,
        )

    def _request_model(
        self,
        material_input: MaterialInput,
    ) -> VisionResponsePayload:
        encoded_image = base64.b64encode(
            material_input.content
        ).decode("ascii")

        data_url = (
            f"data:{material_input.material.media_type};"
            f"base64,{encoded_image}"
        )

        request_body = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "请检查这份光伏投保图片。"
                                "材料类别："
                                f"{material_input.material.category.value}。"
                                "请按照 JSON 格式返回识别结果。"
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": data_url
                            },
                        },
                    ],
                },
            ],
            "temperature": 0,
            "enable_thinking": False,
            "response_format": {
                "type": "json_object",
            },
        }

        try:
            with httpx.Client(
                timeout=(
                    self._settings.timeout_seconds
                ),
                transport=self._transport,
            ) as client:
                response = client.post(
                    (
                        f"{self._settings.base_url}"
                        "/chat/completions"
                    ),
                    headers={
                        "Authorization": (
                            "Bearer "
                            f"{self._settings.api_key}"
                        ),
                        "Content-Type": (
                            "application/json"
                        ),
                    },
                    json=request_body,
                )

                response.raise_for_status()

        except httpx.TimeoutException as exc:
            raise ProviderError(
                "vision provider request timed out"
            ) from exc

        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                "vision provider returned HTTP "
                f"{exc.response.status_code}"
            ) from exc

        except httpx.RequestError as exc:
            raise ProviderError(
                "vision provider request failed"
            ) from exc

        return self._parse_response(response)

    def _parse_response(
        self,
        response: httpx.Response,
    ) -> VisionResponsePayload:
        try:
            response_data: Any = response.json()

            content = response_data[
                "choices"
            ][0]["message"]["content"]

            if not isinstance(content, str):
                raise TypeError

            json_text = self._extract_json_object(
                content
            )

        except (
            json.JSONDecodeError,
            KeyError,
            IndexError,
            TypeError,
        ) as exc:
            raise ProviderError(
                "vision provider returned "
                "an invalid response"
            ) from exc

        try:
            return (
                VisionResponsePayload
                .model_validate_json(json_text)
            )

        except ValidationError as exc:
            summary = self._validation_error_summary(
                exc
            )

            raise ProviderError(
                "vision provider returned invalid "
                f"response fields: {summary}"
            ) from exc

    @staticmethod
    def _extract_json_object(
        content: str,
    ) -> str:
        stripped = content.strip()
        first_brace = stripped.find("{")
        last_brace = stripped.rfind("}")

        if (
            first_brace == -1
            or last_brace <= first_brace
        ):
            raise json.JSONDecodeError(
                "JSON object not found",
                stripped,
                0,
            )

        return stripped[
            first_brace:last_brace + 1
        ]

    @staticmethod
    def _validation_error_summary(
        error: ValidationError,
    ) -> str:
        issues: list[str] = []

        for item in error.errors(
            include_url=False,
            include_context=False,
            include_input=False,
        )[:5]:
            location = ".".join(
                str(part)
                for part in item["loc"]
            )
            issues.append(
                f"{location}:{item['type']}"
            )

        return ", ".join(issues) or "unknown validation error"

    def _to_risk_findings(
        self,
        *,
        material_id: str,
        response_payload: VisionResponsePayload,
    ) -> list[RiskFinding]:
        findings: list[RiskFinding] = []

        for index, item in enumerate(
            response_payload.findings,
            start=1,
        ):
            if item.detection_status in {
                DetectionStatus.NOT_DETECTED,
                DetectionStatus.NOT_APPLICABLE,
            }:
                continue

            low_confidence = (
                item.confidence
                < self._confidence_threshold
            )

            detection_status = (
                DetectionStatus.UNCERTAIN
                if low_confidence
                else item.detection_status
            )

            findings.append(
                RiskFinding(
                    finding_id=(
                        f"{material_id}:"
                        f"{item.category.value}:"
                        f"{index}"
                    ),
                    material_id=material_id,
                    category=item.category,
                    label=item.label,
                    detection_status=(
                        detection_status
                    ),
                    severity=item.severity,
                    confidence=item.confidence,
                    bbox=item.bbox,
                    evidence_text=(
                        item.evidence_text
                    ),
                    provider=self.name,
                    model=self.model_name,
                    requires_manual_review=(
                        item.requires_manual_review
                        or detection_status
                        is DetectionStatus.UNCERTAIN
                    ),
                )
            )

        return findings
