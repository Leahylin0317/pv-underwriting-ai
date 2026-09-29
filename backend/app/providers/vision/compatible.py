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

from ..common import (
    MaterialInput,
    ProviderError,
    post_with_connect_retry,
)
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
材料类别用于限定可判断范围；不要把没有拍到、看不清或被遮挡的区域判为未发现。
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

detection_status 只能是 detected、not_detected、uncertain 或 not_applicable。
severity 只能是 info、low、medium、high、critical、unknown。
confidence 必须是 0 到 1 之间的小数。
requires_manual_review 必须是 true 或 false。

bbox 无法可靠定位时必须返回 null。
bbox 能够可靠定位时必须是 JSON 对象，并且必须包含：
x_min、y_min、x_max、y_max、coordinate_space。
坐标必须是 0 到 1 之间的归一化小数。
coordinate_space 必须固定为 normalized_0_1。

对于 panorama 全景照，必须分别检查以下 8 类拒保环境，并为每类返回一项状态：
agriculture_environment、forest_environment、livestock_environment、
fishery_environment、water_adjacent_environment、tidal_flat_environment、
mountain_environment、desertification_environment。
只有画面覆盖充分且能够排除该类风险时才能返回 not_detected；画面未覆盖、模糊、
夜拍或证据不足时返回 uncertain，并说明需要补拍的视角。
对其他材料只检查该材料能支持判断的风险类别。已检查且视野充分但未发现风险时，
返回对应类别的 not_detected；不适用的类别可省略或标记 not_applicable。
每张受检图片都必须返回一项 image_quality：清晰、光线足且覆盖检查区域时为 not_detected；
模糊、过暗、关键区域裁切或视角不符时为 detected；无法确认时为 uncertain。图片质量不足
时不得把风险项判为 not_detected。
屋顶连接处必须评估安装载体并返回 installation_type，并检查可见连接件松脱、锈蚀或缺失
（roof_connection_abnormal）；组件照片只检查肉眼可见的破裂、缺角或明显脱层
（module_damage），不得推断电气性能或热斑；逆变器照片检查外壳破损、严重锈蚀、
裸露线缆或明确故障指示（inverter_abnormal）。电气接地照片只检查可见断开、裸露或
严重腐蚀（electrical_grounding_abnormal），不能仅凭外观宣称接地电阻合格。
组件表面照片（component_surface）还要检查组件背板鼓包、明显变色和表面破损；照片未展示背面时
不得推断背板状态。屋顶连接处照片需检查可见支架锈蚀、变形和防水层损坏；这些阶段二发现只作为
风险提示和人工复核依据，不要自行推导费率。
女儿墙照片必须评估
missing_parapet_or_guardrail 与 drainage_abnormal；车间照片必须评估易燃物和危险品；
汇流箱照片必须评估 combiner_box_seal_abnormal、combiner_box_fuse_abnormal、
surge_protector_abnormal。
电气系统照片如能清晰看到线缆，必须检查是否裸露且无保护（unprotected_cable）；若存在，应明确
报告可见证据。车间照片还要识别危险工艺（dangerous_process）、洁净车间（cleanroom）及消防
设施缺失或异常（fire_protection_absent）；环境未拍到或证据不足时必须返回 uncertain。
监控区域材料必须评估监控是否有效覆盖光伏阵列（monitoring_effective_coverage）；仅凭摄像头存在
不能认定覆盖有效，需结合覆盖示意或画面证据，无法确认时返回 uncertain。
如果屋顶连接处照片中直接可见涉水、农业、林地、畜牧、渔业、滩涂、山地或沙化环境，必须返回
对应环境类别；未拍到完整周边时不得据此返回 not_detected。
installation_type 用于报告照片观察到的安装载体（彩钢瓦屋顶、平屋顶、瓦片屋顶、车棚顶）。
严重遮挡、通道阻塞、缺少女儿墙/护栏、排水异常、易燃物和危险品均需明确返回状态。

不要将未检查的项目伪装成 not_detected。
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
        quality_preflight = (
            "、".join(material_input.material.quality_issues)
            or "未发现明显预检异常；这不等于图片质量已通过"
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
