import base64
import json
from typing import Any

import httpx
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
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
只根据图片中能够观察到的证据进行判断，不得猜测或补充图片外的信息。
返回一个 JSON 对象，顶层字段固定为 findings。
findings 是数组，每个元素必须包含：
category、label、detection_status、severity、confidence、bbox、evidence_text、requires_manual_review。
category 只能是以下风险类别之一：{RISK_CATEGORY_VALUES}。
detection_status 只能是 detected 或 uncertain。
severity 只能是 info、low、medium、high、critical、unknown。
confidence 必须是 0 到 1 之间的小数。
bbox 无法可靠定位时返回 null；能够定位时使用 0 到 1 的归一化坐标。
如果没有发现风险，返回 {{"findings": []}}。
不要返回 Markdown，不要返回 JSON 以外的解释。
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

            return (
                VisionResponsePayload
                .model_validate_json(json_text)
            )

        except (
            json.JSONDecodeError,
            KeyError,
            IndexError,
            TypeError,
            ValidationError,
        ) as exc:
            raise ProviderError(
                "vision provider returned "
                "an invalid response"
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
