"""Location evidence must not silently become an automatic rejection."""

from datetime import UTC, date, datetime

import httpx
from app.contracts import (
    Material,
    MaterialCategory,
    MaterialParseStatus,
    MaterialQualityStatus,
    OcrField,
    ProjectInfo,
    WatermarkStatus,
    WeatherProfile,
)
from app.location import AmapGeocoder, GeocodeResult, assess_location
from app.pipeline import UnderwritingPipeline
from app.providers import MaterialInput, MockOcrProvider, VisionProvider
from app.providers.weather import WeatherProvider


def project(*, address: str | None = None) -> ProjectInfo:
    return ProjectInfo(
        project_name=None,
        insured_name=None,
        project_type="rooftop",
        installation_type="flat_roof",
        site_address=address,
        longitude=None,
        latitude=None,
        proposed_start_date=None,
        component_model=None,
    )


def material(material_id: str, category: MaterialCategory, *,
             longitude: float | None = None, latitude: float | None = None) -> Material:
    return Material(
        material_id=material_id,
        category=category,
        file_name=material_id + ".jpg",
        media_type="image/jpeg",
        quality_status=MaterialQualityStatus.USABLE,
        quality_issues=[],
        parse_status=MaterialParseStatus.SUCCESS,
        watermark_status="present" if longitude is not None or category is MaterialCategory.PANORAMA else "not_checked",
        longitude=longitude,
        latitude=latitude,
    )


def address_field(material_id: str, address: str, *, field_name: str = "site_address") -> OcrField:
    return OcrField(
        field_id=material_id + ":address",
        material_id=material_id,
        field_name=field_name,
        raw_value=address,
        normalized_value=address,
        value_status="extracted",
        confidence=0.98,
        provider="test",
        model="test",
    )


class PreciseGeocoder:
    def lookup(self, address: str, *, city: str | None = None) -> GeocodeResult | None:
        del city
        if "甲" in address:
            return GeocodeResult(116.397, 39.908, "门牌号", address, True)
        return GeocodeResult(121.474, 31.230, "门牌号", address, True)


class CoarseGeocoder:
    def lookup(self, address: str, *, city: str | None = None) -> GeocodeResult | None:
        del city
        return GeocodeResult(116.397, 39.908, "区县", address, False)


def test_one_photo_coordinate_is_candidate_but_not_verified() -> None:
    result, coordinates = assess_location(
        project(), [material("photo", MaterialCategory.PANORAMA,
                             longitude=116.397, latitude=39.908)], []
    )
    assert result.status == "single_source"
    assert coordinates == (116.397, 39.908)
    assert not result.weather_coordinates_verified
    assert result.missing_requirements


def test_unconfirmed_photo_coordinates_are_not_location_evidence() -> None:
    photo = material("photo", MaterialCategory.PANORAMA,
                     longitude=116.397, latitude=39.908)
    photo = photo.model_copy(update={"watermark_status": WatermarkStatus.NOT_CHECKED})
    result, coordinates = assess_location(project(), [photo], [])
    assert result.status == "missing"
    assert coordinates is None


def test_two_photo_coordinates_match_or_conflict() -> None:
    photo = material("photo-1", MaterialCategory.PANORAMA,
                     longitude=116.397, latitude=39.908)
    nearby = material("photo-2", MaterialCategory.PANORAMA,
                      longitude=116.398, latitude=39.909)
    distant = material("photo-3", MaterialCategory.PANORAMA,
                       longitude=121.474, latitude=31.230)
    matched, coordinate = assess_location(project(), [photo, nearby], [])
    assert matched.status == "uncertain"  # Two photos alone cannot verify the insured site.
    assert not matched.weather_coordinates_verified
    assert coordinate == (116.397, 39.908)

    conflict, coordinate = assess_location(project(), [photo, distant], [])
    assert conflict.status == "conflict"
    assert coordinate is None
    assert "photo-1" in conflict.notes[0]
    assert "photo-3" in conflict.notes[0]


def test_submitted_site_and_photo_coordinates_can_verify_each_other() -> None:
    submitted = project()
    submitted = submitted.model_copy(update={"longitude": 116.397, "latitude": 39.908})
    photo = material("photo", MaterialCategory.PANORAMA,
                     longitude=116.398, latitude=39.909)
    result, _ = assess_location(submitted, [photo], [])
    assert result.status == "verified"
    assert result.weather_coordinates_verified


def test_address_and_photo_coordinate_need_precise_geocoding() -> None:
    filing = material("filing", MaterialCategory.FILING_CERTIFICATE)
    photo = material("photo", MaterialCategory.PANORAMA,
                     longitude=116.397, latitude=39.908)
    fields = [address_field("filing", "北京市甲路1号")]
    without_map, _ = assess_location(project(), [filing, photo], fields)
    assert without_map.status == "uncertain"
    assert "未配置" in without_map.notes[0]

    precise, _ = assess_location(project(), [filing, photo], fields,
                                 geocoder=PreciseGeocoder())
    assert precise.status == "verified"

    coarse, _ = assess_location(project(), [filing, photo], fields,
                                geocoder=CoarseGeocoder())
    assert coarse.status == "uncertain"


def test_address_coordinate_conflict_is_only_a_warning_candidate() -> None:
    filing = material("filing", MaterialCategory.FILING_CERTIFICATE)
    photo = material("photo", MaterialCategory.PANORAMA,
                     longitude=121.474, latitude=31.230)
    result, coordinates = assess_location(
        project(), [filing, photo], [address_field("filing", "北京市甲路1号")],
        geocoder=PreciseGeocoder(),
    )
    assert result.status == "conflict"
    assert coordinates is None
    assert "需核对原件" in result.notes[0]


def test_one_address_can_offer_a_weather_candidate_without_being_verified() -> None:
    filing = material("filing", MaterialCategory.FILING_CERTIFICATE)
    result, coordinates = assess_location(
        project(), [filing], [address_field("filing", "北京市甲路1号")],
        geocoder=PreciseGeocoder(),
    )
    assert result.status == "single_source"
    assert coordinates is not None
    assert not result.weather_coordinates_verified
    assert result.evidence[0].geocode_level == "门牌号"


def test_matching_textual_photo_address_and_filing_address() -> None:
    filing = material("filing", MaterialCategory.FILING_CERTIFICATE)
    photo = material("photo", MaterialCategory.PANORAMA)
    result, coordinates = assess_location(
        project(), [filing, photo], [
            address_field("filing", "北京市甲路1号"),
            address_field("photo", "北京市甲路1号", field_name="watermark_address"),
        ],
    )
    assert result.status == "verified"
    assert coordinates is None  # An address alone is not a latitude/longitude.


def test_amap_project_env_fallback_and_environment_priority(monkeypatch, tmp_path) -> None:
    project_env = tmp_path / ".env"
    project_env.write_text(
        "PV_AMAP_WEB_SERVICE_KEY=project-env-test-key\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("app.location.geocoding.PROJECT_ENV_PATH", project_env)
    monkeypatch.delenv("PV_AMAP_WEB_SERVICE_KEY", raising=False)
    assert AmapGeocoder.from_environment().key == "project-env-test-key"
    monkeypatch.setenv("PV_AMAP_WEB_SERVICE_KEY", "project-test-key")
    assert AmapGeocoder.from_environment().key == "project-test-key"


def test_amap_geocoder_requires_one_precise_result() -> None:
    responses = [
        {"status": "1", "geocodes": [{"location": "116.397,39.908", "level": "门牌号",
                                       "formatted_address": "北京市甲路1号"}]},
        {"status": "1", "geocodes": [{"location": "116.397,39.908", "level": "区县",
                                       "formatted_address": "北京市"}]},
        {"status": "1", "geocodes": [{"location": "116.397,39.908", "level": "门牌号"},
                                      {"location": "121.474,31.230", "level": "门牌号"}]},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(AmapGeocoder.URL)
        assert request.url.params["address"] == "北京市甲路1号"
        return httpx.Response(200, request=request, json=responses.pop(0))

    geocoder = AmapGeocoder(
        "test-key",
        transport=httpx.MockTransport(handler),
    )
    assert geocoder.lookup("北京市甲路1号").precise
    assert not geocoder.lookup("北京市甲路1号").precise
    assert geocoder.lookup("北京市甲路1号") is None


class NoFindings(VisionProvider):
    @property
    def name(self) -> str:
        return "no-findings"

    @property
    def model_name(self) -> str:
        return "test"

    def analyze(self, material_input: MaterialInput) -> list:
        del material_input
        return []


class RecordingWeather(WeatherProvider):
    def __init__(self) -> None:
        self.calls: list[tuple[float, float]] = []

    @property
    def name(self) -> str:
        return "recording-weather"

    def lookup(self, *, longitude: float, latitude: float) -> WeatherProfile:
        self.calls.append((longitude, latitude))
        return WeatherProfile(
            longitude=longitude,
            latitude=latitude,
            historical_max_wind_m_s=20,
            historical_max_hail_mm=None,
            historical_max_snow_load_pa=None,
            observation_start=date(2020, 1, 1),
            observation_end=date(2025, 1, 1),
            source_name="test",
            source_url=None,
            retrieved_at=datetime.now(UTC),
        )


def test_pipeline_queries_candidate_weather_but_requires_second_location_source() -> None:
    weather = RecordingWeather()
    pipeline = UnderwritingPipeline(
        ocr_provider=MockOcrProvider(),
        vision_provider=NoFindings(),
        weather_provider=weather,
    )
    photo = material("photo", MaterialCategory.PANORAMA,
                     longitude=116.397, latitude=39.908)
    case = pipeline.run(
        case_id="one-location",
        project=project(),
        materials=[MaterialInput(material=photo, content=b"test")],
    )
    assert weather.calls == [(116.397, 39.908)]
    assert case.location_assessment.status == "single_source"
    assert not case.location_assessment.weather_coordinates_verified
    assert case.decision.decision.value == "request_more"


def test_pipeline_pauses_weather_and_never_auto_rejects_on_location_conflict() -> None:
    weather = RecordingWeather()
    pipeline = UnderwritingPipeline(
        ocr_provider=MockOcrProvider(),
        vision_provider=NoFindings(),
        weather_provider=weather,
    )
    photos = [
        material("photo-1", MaterialCategory.PANORAMA, longitude=116.397, latitude=39.908),
        material("photo-2", MaterialCategory.PANORAMA, longitude=121.474, latitude=31.230),
    ]
    case = pipeline.run(
        case_id="conflicting-location",
        project=project(),
        materials=[MaterialInput(material=item, content=b"test") for item in photos],
    )
    assert weather.calls == []
    assert case.location_assessment.status == "conflict"
    assert case.decision.decision.value == "manual_review"
