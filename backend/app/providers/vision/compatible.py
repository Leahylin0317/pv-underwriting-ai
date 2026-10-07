import base64
import json
from pathlib import Path
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
from app.prompts.vision import builtin_bundle, compose_prompt, load_bundle
from app.providers.routing import SCENE_PHOTO_CATEGORIES
from app.settings import VlmSettings

from ..common import (
    MaterialInput,
    ProviderError,
    post_with_connect_retry,
)
from .base import VisionAnalysis, VisionProvider

SUPPORTED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
}

DEFAULT_CONFIDENCE_THRESHOLD = 0.65

RISK_CATEGORY_VALUES = "、".join(
    category.value
    for category in RiskCategory
)

SYSTEM_PROMPT = builtin_bundle()['prompt']


PROMPT_DEFAULT_PATH = Path(__file__).resolve().parents[4] / "data" / "vision_prompt_default.json"


def default_prompt() -> str:
    return load_bundle(PROMPT_DEFAULT_PATH)['prompt']


def material_prompt(category) -> str:
    bundle = load_bundle(PROMPT_DEFAULT_PATH)
    return compose_prompt(bundle['prompt'], bundle['specialized_prompts'].get(category.value, ''), category)


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
    watermark_present: bool | None = None
    watermark_bbox: Bbox | None = None
    watermark_evidence: str | None = None


class CompatibleVisionProvider(VisionProvider):
    """调用 OpenAI Chat Completions 兼容接口的视觉识别 Provider。"""

    def __init__(
        self,
        settings: VlmSettings,
        *,
        transport: httpx.BaseTransport | None = None,
        system_prompt: str | None = None,
        confidence_threshold: float = (
            DEFAULT_CONFIDENCE_THRESHOLD
        ),
    ) -> None:
        if not 0.0 <= confidence_threshold <= 1.0:
            raise ValueError(
                "confidence_threshold must be "
                "between zero and one"
            )

        self._system_prompt = system_prompt
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
        return self.analyze_with_watermark(material_input).findings

    def analyze_with_watermark(
        self,
        material_input: MaterialInput,
    ) -> VisionAnalysis:
        material = material_input.material

        if material.media_type not in SUPPORTED_IMAGE_TYPES:
            return VisionAnalysis(findings=[])

        if not material_input.content:
            raise ProviderError(
                "vision provider received an empty image"
            )

        try:
            response_payload = self._request_model(material_input)
        except ProviderError as exc:
            # Only retry a malformed response; never turn failed validation into findings.
            if not str(exc).startswith(('vision provider returned invalid response fields:',
                                        'vision provider returned an invalid response')):
                raise
            response_payload = self._request_model(material_input, repair_hint=str(exc))

        return VisionAnalysis(
            findings=self._to_risk_findings(
                material_id=material.material_id,
                response_payload=response_payload,
            ),
            watermark_bbox=response_payload.watermark_bbox,
            watermark_evidence=response_payload.watermark_evidence,
            watermark_present=(
                response_payload.watermark_present
                if material.category in SCENE_PHOTO_CATEGORIES else None
            ),
        )

    def _request_model(
        self,
        material_input: MaterialInput,
        *, repair_hint: str | None = None,
    ) -> VisionResponsePayload:
        encoded_image = base64.b64encode(
            material_input.content
        ).decode("ascii")

        data_url = (
            f"data:{material_input.material.media_type};"
            f"base64,{encoded_image}"
        )
        quality_preflight = (
            "、".join(material_input.material.quality_issues)
            or "未发现明显预检异常；这不等于图片质量已通过"
        )

        request_body = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": self._system_prompt if self._system_prompt is not None else material_prompt(material_input.material.category),
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
                                "文件预检质量提示："
                                f"{quality_preflight}。"
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

        if repair_hint:
            request_body['messages'].append({
                'role': 'user',
                'content': '上次输出未通过格式校验：' + repair_hint +
                    '。请重新检查同一图片，严格遵守输出字段和枚举。'
                    '无法可靠定位的 bbox 必须为 null，不能提供零面积框。'
                    '不要编造结论来满足格式。只返回合法 JSON。',
            })

        try:
            with httpx.Client(
                timeout=httpx.Timeout(
                    self._settings.timeout_seconds,
                    connect=min(
                        self._settings.timeout_seconds,
                        15.0,
                    ),
                ),
                transport=self._transport,
                trust_env=self._settings.trust_env,
            ) as client:
                response = post_with_connect_retry(
                    client,
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

        except httpx.ConnectTimeout as exc:
            raise ProviderError(
                "vision provider connection timed out"
            ) from exc

        except httpx.ReadTimeout as exc:
            raise ProviderError(
                "vision provider response timed out"
            ) from exc

        except httpx.TimeoutException as exc:
            raise ProviderError(
                "vision provider request timed out"
            ) from exc

        except httpx.ConnectError as exc:
            raise ProviderError(
                "vision provider connection failed"
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
            low_confidence = (
                item.confidence
                < self._confidence_threshold
            )

            detection_status = (
                DetectionStatus.UNCERTAIN
                if low_confidence and item.detection_status is not DetectionStatus.NOT_APPLICABLE
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
