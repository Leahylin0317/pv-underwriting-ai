"""Conservative, auditable comparison of independent site-location evidence."""

from dataclasses import dataclass
from math import asin, cos, pi, radians, sin, sqrt
from typing import Literal, Protocol

from pydantic import Field

from app.contracts.common import ContractModel
from app.contracts.enums import MaterialCategory, OcrValueStatus, WatermarkStatus
from app.contracts.inputs import Material, OcrField, ProjectInfo

from .geocoding import GeocodeResult

LocationStatus = Literal["verified", "single_source", "conflict", "uncertain", "missing"]


class LocationEvidence(ContractModel):
    source: str
    material_id: str | None = None
    file_name: str | None = None
    address: str | None = None
    longitude: float | None = None
    latitude: float | None = None
    geocode_level: str | None = None
    coordinate_system: str | None = None


class LocationAssessment(ContractModel):
    status: LocationStatus
    evidence: list[LocationEvidence] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    weather_coordinate_source: str | None = None
    weather_coordinates_verified: bool = False


class Geocoder(Protocol):
    def lookup(self, address: str, *, city: str | None = None) -> GeocodeResult | None: ...


@dataclass
class _Source:
    source: str
    material_id: str | None
    file_name: str | None = None
    is_photo: bool = False
    address: str | None = None
    longitude: float | None = None
    latitude: float | None = None
    geocode_level: str | None = None
    geocoded: bool = False

    def as_evidence(self) -> LocationEvidence:
        return LocationEvidence(
            source=self.source,
            material_id=self.material_id,
            file_name=self.file_name,
            address=self.address,
            longitude=self.longitude,
            latitude=self.latitude,
            geocode_level=self.geocode_level,
            coordinate_system="GCJ-02" if self.geocoded else (
                "未标明" if self.longitude is not None else None
            ),
        )


def _normalized_address(value: str) -> str:
    return "".join(char for char in value.casefold() if char.isalnum())


def _is_detailed_address(value: str) -> bool:
    normalized = _normalized_address(value)
    return len(normalized) >= 6 and any(
        marker in normalized for marker in ("号", "路", "街", "村", "园区", "厂", "大厦", "镇")
    )


def _gcj_to_wgs84(longitude: float, latitude: float) -> tuple[float, float]:
    """Approximate mainland GCJ-02 to WGS-84 for weather-grid lookup."""
    if not (72.004 <= longitude <= 137.8347 and 0.8293 <= latitude <= 55.8271):
        return longitude, latitude
    x, y = longitude - 105.0, latitude - 35.0
    dlat = (-100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y
            + 0.2 * sqrt(abs(x)) + (20 * sin(6 * x * pi) + 20 * sin(2 * x * pi)) * 2 / 3
            + (20 * sin(y * pi) + 40 * sin(y / 3 * pi)) * 2 / 3
            + (160 * sin(y / 12 * pi) + 320 * sin(y * pi / 30)) * 2 / 3)
    dlon = (300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y
            + 0.1 * sqrt(abs(x)) + (20 * sin(6 * x * pi) + 20 * sin(2 * x * pi)) * 2 / 3
            + (20 * sin(x * pi) + 40 * sin(x / 3 * pi)) * 2 / 3
            + (150 * sin(x / 12 * pi) + 300 * sin(x / 30 * pi)) * 2 / 3)
    rad_lat = latitude / 180 * pi
    magic = 1 - 0.00669342162296594323 * sin(rad_lat) ** 2
    sqrt_magic = sqrt(magic)
    dlat = dlat * 180 / ((6378245.0 * (1 - 0.00669342162296594323))
                          / (magic * sqrt_magic) * pi)
    dlon = dlon * 180 / (6378245.0 / sqrt_magic * cos(rad_lat) * pi)
    return longitude - dlon, latitude - dlat


def _distance_km(left: _Source, right: _Source) -> float:
    lat1, lon1, lat2, lon2 = map(
        radians, (left.latitude, left.longitude, right.latitude, right.longitude)
    )
    delta_lat, delta_lon = lat2 - lat1, lon2 - lon1
    value = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    return 12742 * asin(min(1.0, sqrt(value)))


def assess_location(
    project: ProjectInfo,
    materials: list[Material],
    ocr_fields: list[OcrField],
    *,
    geocoder: Geocoder | None = None,
) -> tuple[LocationAssessment, tuple[float, float] | None]:
    """Return a location verdict and optional weather candidate (longitude, latitude).

    Distance bands are screening heuristics, not automatic rejection thresholds. Amap
    returns GCJ-02 while photo coordinates may use a different datum; the 1/5 km
    bands deliberately avoid treating small offsets as confirmed discrepancies.
    """
    sources: dict[str, _Source] = {}
    if project.site_address or (project.longitude is not None and project.latitude is not None):
        sources["submission"] = _Source(
            source="投保标的",
            material_id=None,
            address=project.site_address,
            longitude=project.longitude,
            latitude=project.latitude,
        )
    materials_by_id = {item.material_id: item for item in materials}
    categories = {item.material_id: item.category for item in materials}
    file_names = {item.material_id: item.file_name for item in materials}
    for material in materials:
        if (material.watermark_status is WatermarkStatus.PRESENT
            and material.longitude is not None and material.latitude is not None):
            sources[material.material_id] = _Source(
                source="现场照片水印",
                material_id=material.material_id,
                file_name=material.file_name,
                is_photo=True,
                longitude=material.longitude,
                latitude=material.latitude,
            )

    for field in ocr_fields:
        if (
            field.value_status is not OcrValueStatus.EXTRACTED
            or field.confidence < 0.65
        ):
            continue
        address = (field.normalized_value or field.raw_value or "").strip()
        if not address:
            continue
        category = categories.get(field.material_id)
        official = category in {
            MaterialCategory.PROJECT_DOCUMENT, MaterialCategory.FILING_CERTIFICATE,
            MaterialCategory.GRID_CONNECTION_DOCUMENT,
        }
        photo = category not in {None, MaterialCategory.PROJECT_DOCUMENT, MaterialCategory.FILING_CERTIFICATE,
                                 MaterialCategory.GRID_CONNECTION_DOCUMENT,
                                 MaterialCategory.EQUIPMENT_INVENTORY}
        if photo and materials_by_id[field.material_id].watermark_status is not WatermarkStatus.PRESENT:
            continue
        if not ((official and field.field_name == "site_address") or
                (photo and field.field_name == "watermark_address")):
            continue
        source = sources.setdefault(
            field.material_id,
            _Source(
                source="备案/并网材料" if official else "现场照片水印",
                material_id=field.material_id,
                file_name=file_names[field.material_id],
                is_photo=photo,
            ),
        )
        source.address = address

    if not sources:
        return LocationAssessment(
            status="missing",
            missing_requirements=["补充项目地址及带位置水印的现场照片"],
        ), None

    cache: dict[str, GeocodeResult | None] = {}
    internal_conflicts: list[str] = []
    for source in sources.values():
        if not source.address or geocoder is None:
            continue
        key = _normalized_address(source.address)
        if key not in cache:
            cache[key] = geocoder.lookup(source.address, city=project.city)
        match = cache[key]
        if match is not None:
            source.geocode_level = match.level
            if match.precise:
                if source.longitude is not None and source.latitude is not None:
                    geocoded_point = _Source(source="地图定位", material_id=source.material_id,
                                             longitude=match.longitude, latitude=match.latitude)
                    if _distance_km(source, geocoded_point) > 5.0:
                        internal_conflicts.append(
                            f"{source.source}（{source.file_name or '投保信息'}）内部地址与坐标明显不符，需核对原件"
                        )
                else:
                    source.longitude = match.longitude
                    source.latitude = match.latitude
                    source.geocoded = True

    comparable = 0
    consistent = 0
    cross_origin_agreement = False
    conflicts: list[str] = internal_conflicts
    values = list(sources.values())
    for index, left in enumerate(values):
        for right in values[index + 1:]:
            if (left.address and right.address
                and _is_detailed_address(left.address)
                and _normalized_address(left.address) == _normalized_address(right.address)):
                comparable += 1
                consistent += 1
                cross_origin_agreement = cross_origin_agreement or left.is_photo != right.is_photo
            if (
                left.longitude is not None and left.latitude is not None
                and right.longitude is not None and right.latitude is not None
            ):
                distance = _distance_km(left, right)
                comparable += 1
                if distance <= 1.0:
                    consistent += 1
                    cross_origin_agreement = cross_origin_agreement or left.is_photo != right.is_photo
                elif distance > 5.0:
                    conflicts.append(
                        f"{left.source}（{left.file_name or '投保信息'}）与"
                        f"{right.source}（{right.file_name or '投保信息'}）位置相距约 {distance:.1f} 公里，需核对原件"
                    )

    if conflicts:
        status: LocationStatus = "conflict"
        notes = conflicts
        missing = ["核对位置冲突的原始材料；确认异地前不自动拒保"]
    elif len(sources) == 1:
        status = "single_source"
        notes = ["仅有一份独立位置来源，无法交叉核验是否为同一电站"]
        missing = ["补充另一份独立的位置材料以核验电站位置"]
    elif consistent:
        status = "verified" if comparable == consistent and cross_origin_agreement else "uncertain"
        if status == "verified":
            notes = ["项目地址材料与现场照片的位置一致"]
            missing = []
        elif not cross_origin_agreement:
            notes = ["同类材料位置一致，但尚未完成项目地址与现场照片的交叉核验"]
            missing = ["补充另一类独立位置材料：项目地址或带位置水印的现场照片"]
        else:
            notes = ["部分位置证据一致，仍有未解释的差异"]
            missing = ["人工核对位置证据差异"]
    else:
        status = "uncertain"
        needs_address_coordinates = any(item.address and item.longitude is None for item in values) and any(
            item.longitude is not None for item in values
        )
        notes = [
            "地址与坐标需要地图定位服务；当前未配置，无法自动比较"
            if needs_address_coordinates and geocoder is None
            else "多份材料的位置无法可靠比对，可能缺少精确地址或地图定位结果"
        ]
        missing = ["补充精确位置材料或人工核对地址与坐标"]

    candidate: _Source | None = None
    if status != "conflict":
        # Prefer an actual photo coordinate to an approximate geocoded address.
        candidate = next(
            (item for item in values if item.material_id and not item.geocoded
             and item.longitude is not None and item.latitude is not None), None
        )
        if candidate is None:
            candidate = next(
                (item for item in values if not item.geocoded
                 and item.longitude is not None and item.latitude is not None), None
            )
        if candidate is None:
            candidate = next(
                (item for item in values if item.longitude is not None and item.latitude is not None), None
            )
    coordinates = None
    if candidate is not None:
        coordinates = (
            _gcj_to_wgs84(candidate.longitude, candidate.latitude)
            if candidate.geocoded else (candidate.longitude, candidate.latitude)
        )
    assessment = LocationAssessment(
        status=status,
        evidence=[item.as_evidence() for item in values],
        notes=notes,
        missing_requirements=missing,
        weather_coordinate_source=(
            f"{candidate.source}（{candidate.file_name or '投保信息'}）" if candidate else None
        ),
        weather_coordinates_verified=status == "verified" and candidate is not None,
    )
    return assessment, coordinates
