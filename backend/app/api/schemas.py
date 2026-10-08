from collections import Counter
from typing import Literal, Self
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator

from app.contracts import (
    CaptureView,
    ContractModel,
    DecisionType,
    InstallationType,
    Material,
    MaterialCategory,
    ProjectInfo,
    SentinelContextRecord,
)


class MockAnalyzeRequest(ContractModel):
    """Mock 核保接口接收的请求数据。"""

    case_id: str = Field(min_length=1)
    project: ProjectInfo
    materials: list[Material] = Field(
        min_length=1
    )


class UploadedMaterialManifest(
    ContractModel
):
    """一份上传文件对应的材料信息。"""

    material_id: str = Field(min_length=1)
    category: MaterialCategory
    capture_view: CaptureView = CaptureView.UNKNOWN


class RealAnalyzeManifest(ContractModel):
    """真实整单核保接口接收的案件清单。"""

    case_id: str = Field(min_length=1)
    project: ProjectInfo
    materials: list[
        UploadedMaterialManifest
    ] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_material_ids(self) -> Self:
        material_ids = [
            material.material_id
            for material in self.materials
        ]

        duplicate_ids = sorted(
            material_id
            for material_id, count
            in Counter(material_ids).items()
            if count > 1
        )

        if duplicate_ids:
            raise ValueError(
                "duplicate material IDs in "
                f"manifest: {duplicate_ids}"
            )

        return self


class HumanReviewSubmission(ContractModel):
    """A human underwriting decision recorded against a saved case."""

    reviewer_name: str = Field(min_length=1, max_length=100)
    final_decision: DecisionType
    comment: str = Field(min_length=1, max_length=4000)

    @field_validator("reviewer_name", "comment")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @model_validator(mode="after")
    def require_final_outcome(self) -> Self:
        if self.final_decision is DecisionType.MANUAL_REVIEW:
            raise ValueError("final_decision must be a completed underwriting outcome")
        return self


class MapReviewPreparationRequest(ContractModel):
    """用户同意将本次地图复核地址发给地图服务进行地理编码。"""

    acknowledged_address_transfer: bool
    address: str | None = Field(default=None, min_length=1, max_length=128)
    address_source: Literal[
        "project_info",
        "material_ocr",
        "human_corrected",
    ] = "project_info"

    @model_validator(mode="after")
    def require_external_address_consent(self) -> Self:
        if not self.acknowledged_address_transfer:
            raise ValueError("external address transfer must be acknowledged")
        return self


class ComponentCorrectionSubmission(ContractModel):
    """A human-confirmed exact-model correction backed by HTTPS source links."""

    component_model: str = Field(min_length=2, max_length=100)
    manufacturer: str = Field(min_length=2, max_length=120)
    rated_power_w: float | None = Field(default=None, gt=0.0)
    hail_resistance_mm: float | None = Field(default=None, gt=0.0)
    hail_impact_velocity_m_s: float | None = Field(default=None, gt=0.0)
    wind_load_pa: float | None = Field(default=None, gt=0.0)
    snow_load_pa: float | None = Field(default=None, gt=0.0)
    front_static_load_pa: float | None = Field(default=None, gt=0.0)
    back_static_load_pa: float | None = Field(default=None, gt=0.0)
    market_version: str | None = Field(default=None, max_length=80)
    source_document_type: str = Field(min_length=2, max_length=100)
    source_url: str = Field(min_length=8, max_length=2000)
    parameter_sources: dict[str, str] = Field(min_length=1)
    source_note: str = Field(min_length=1, max_length=2000)
    reviewer_name: str = Field(min_length=1, max_length=100)
    exact_model_verified: bool

    @field_validator("component_model", "manufacturer", "source_document_type", "source_note", "reviewer_name")
    @classmethod
    def strip_component_correction_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("source_url")
    @classmethod
    def require_https_source(cls, value: str) -> str:
        parsed = urlparse(value.strip())
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("source_url must be a public HTTPS URL")
        return value.strip()

    @field_validator("parameter_sources")
    @classmethod
    def require_https_parameter_sources(cls, value: dict[str, str]) -> dict[str, str]:
        for field_name, url in value.items():
            parsed = urlparse(url.strip())
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
            ):
                raise ValueError(f"parameter source for {field_name} must be HTTPS")
        return {field_name: url.strip() for field_name, url in value.items()}

    @model_validator(mode="after")
    def require_reviewed_field_sources(self) -> Self:
        fields = (
            "rated_power_w",
            "hail_resistance_mm",
            "hail_impact_velocity_m_s",
            "wind_load_pa",
            "snow_load_pa",
            "front_static_load_pa",
            "back_static_load_pa",
        )
        supplied = {field for field in fields if getattr(self, field) is not None}
        if not supplied:
            raise ValueError("at least one component parameter is required")
        unknown = set(self.parameter_sources) - set(fields)
        missing = supplied - set(self.parameter_sources)
        if unknown:
            raise ValueError(f"unknown parameter source fields: {sorted(unknown)}")
        if missing:
            raise ValueError(f"missing parameter sources for: {sorted(missing)}")
        if not self.exact_model_verified:
            raise ValueError("the full model must be verified against the nameplate or datasheet")
        return self


class AmapAddressCandidate(ContractModel):
    formatted_address: str = Field(min_length=1, max_length=300)
    level: str = Field(min_length=1, max_length=60)
    longitude: float = Field(ge=-180.0, le=180.0)
    latitude: float = Field(ge=-90.0, le=90.0)
    amap_longitude: float = Field(ge=-180.0, le=180.0)
    amap_latitude: float = Field(ge=-90.0, le=90.0)
    map_url: str = Field(min_length=1)


class AmapSatelliteMapConfig(ContractModel):
    configured: bool
    api_key: str | None = Field(default=None, repr=False)
    security_js_code: str | None = Field(default=None, repr=False)


class MapReviewSubmission(MapReviewPreparationRequest):
    """记录人工查看地图页面后的补充观察。"""

    selected_candidate: AmapAddressCandidate
    reviewer_name: str = Field(min_length=1, max_length=100)
    map_page_opened: bool
    site_match_confirmed: bool
    photovoltaic_visibility: Literal[
        "visible",
        "not_visible",
        "unclear",
    ]
    observed_installation_type: InstallationType = InstallationType.UNKNOWN
    imagery_capture_date: str | None = Field(
        default=None,
        pattern=r"^\d{4}(-\d{2})?$",
    )
    observations: str = Field(min_length=1, max_length=2000)
    sentinel_context: SentinelContextRecord | None = None

    @field_validator("reviewer_name", "observations")
    @classmethod
    def strip_map_review_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @model_validator(mode="after")
    def require_map_page_review(self) -> Self:
        if not self.map_page_opened:
            raise ValueError("the map page must be opened before recording observations")
        if self.sentinel_context is not None and (
            abs(self.sentinel_context.center_longitude - self.selected_candidate.longitude) > 0.0001
            or abs(self.sentinel_context.center_latitude - self.selected_candidate.latitude) > 0.0001
        ):
            raise ValueError("Sentinel image coordinates must match the selected address")
        return self


class SentinelContextRequest(ContractModel):
    address: str = Field(min_length=1, max_length=128)
    address_source: Literal[
        "project_info",
        "material_ocr",
        "human_corrected",
    ] = "project_info"
    selected_candidate: AmapAddressCandidate
    acknowledged_address_transfer: bool
    acknowledged_coordinate_transfer: bool
    analyze_with_vlm: bool = False
    acknowledged_vlm_transfer: bool = False

    @model_validator(mode="after")
    def require_separate_external_transfer_consents(self) -> Self:
        if not self.acknowledged_address_transfer:
            raise ValueError("Amap address transfer must be acknowledged")
        if not self.acknowledged_coordinate_transfer:
            raise ValueError("Copernicus coordinate transfer must be acknowledged")
        if self.analyze_with_vlm and not self.acknowledged_vlm_transfer:
            raise ValueError("VLM image transfer must be acknowledged")
        return self


class SentinelContextResponse(ContractModel):
    metadata: SentinelContextRecord
    image_base64: str = Field(min_length=1)
    mime_type: Literal["image/png"] = "image/png"


class MapReviewPreparationResponse(ContractModel):
    """供人工核对的高德候选地址和可选卫星图配置。"""

    provider: Literal["amap_maps"] = "amap_maps"
    query_address: str
    candidates: list[AmapAddressCandidate] = Field(min_length=1)
    satellite_map: AmapSatelliteMapConfig
    triggering_material_ids: list[str]
    notice: str


class LoginRequest(ContractModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class UserCreateRequest(ContractModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=12, max_length=256)
    role: Literal["viewer", "underwriter", "admin"]


class UserPasswordResetRequest(ContractModel):
    password: str = Field(min_length=12, max_length=256)
