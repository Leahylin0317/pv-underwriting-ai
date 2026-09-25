import json
from collections.abc import Callable, Iterator
from io import BytesIO

import pymupdf
import pytest
from app.api.ocr_routes import get_ocr_provider
from app.api.routes import get_vision_provider
from app.contracts import (
    DetectionStatus,
    MaterialCategory,
    OcrField,
    OcrValueStatus,
    ProcessingStatus,
    ProcessingStep,
    RiskCategory,
    RiskFinding,
    RiskSeverity,
)
from app.main import app
from app.providers import (
    MaterialInput,
    OcrProvider,
    ProviderError,
    VisionProvider,
)
from fastapi.testclient import TestClient
from PIL import Image

client = TestClient(app)

ProviderOverride = Callable[
    [OcrProvider, VisionProvider],
    None,
]


def png_bytes(
    color: str = "white",
) -> bytes:
    buffer = BytesIO()

    Image.new(
        "RGB",
        (80, 60),
        color=color,
    ).save(
        buffer,
        format="PNG",
    )

    return buffer.getvalue()


def pdf_bytes() -> bytes:
    document = pymupdf.open()

    try:
        page = document.new_page(
            width=300,
            height=200,
        )
        page.insert_text(
            (30, 60),
            "Filing certificate test",
        )
        return document.tobytes()
    finally:
        document.close()


def project_payload() -> dict:
    return {
        "project_name": "真实接口测试项目",
        "insured_name": "示例制造企业有限公司",
        "project_entity": "示例新能源有限公司",
        "project_type": "rooftop",
        "installation_type": "color_steel_roof",
        "site_address": "广东省示例市示例区",
        "province": "广东省",
        "city": "示例市",
        "district": "示例区",
        "longitude": 113.25,
        "latitude": 23.12,
        "proposed_start_date": "2026-10-01",
        "component_model": "PV-MODULE-580W",
    }


def manifest_payload() -> dict:
    return {
        "case_id": "case-real-api-001",
        "project": project_payload(),
        "materials": [
            {
                "material_id": (
                    "material-nameplate-001"
                ),
                "category": (
                    "component_nameplate"
                ),
            },
            {
                "material_id": (
                    "material-panorama-001"
                ),
                "category": "panorama",
            },
        ],
    }


class RecordingOcrProvider(OcrProvider):
    def __init__(self) -> None:
        self.received_inputs: list[
            MaterialInput
        ] = []

    @property
    def name(self) -> str:
        return "recording-ocr-provider"

    @property
    def model_name(self) -> str:
        return "recording-ocr-v1"

    def extract(
        self,
        material_input: MaterialInput,
    ) -> list[OcrField]:
        self.received_inputs.append(
            material_input
        )

        if (
            material_input.material.category
            is not MaterialCategory
            .COMPONENT_NAMEPLATE
        ):
            return []

        return [
            OcrField(
                field_id=(
                    f"{material_input.material.material_id}:"
                    "component_model:1"
                ),
                material_id=(
                    material_input.material.material_id
                ),
                field_name="component_model",
                raw_value="PV-MODULE-580W",
                normalized_value="PV-MODULE-580W",
                value_status=(
                    OcrValueStatus.EXTRACTED
                ),
                confidence=0.98,
                bbox=None,
                provider=self.name,
                model=self.model_name,
                evidence_text=(
                    "Model: PV-MODULE-580W"
                ),
            )
        ]


class RecordingVisionProvider(VisionProvider):
    def __init__(self) -> None:
        self.received_inputs: list[
            MaterialInput
        ] = []

    @property
    def name(self) -> str:
        return "recording-vision-provider"

    @property
    def model_name(self) -> str:
        return "recording-vision-v1"

    def analyze(
        self,
        material_input: MaterialInput,
    ) -> list[RiskFinding]:
        self.received_inputs.append(
            material_input
        )

        if (
            material_input.material.category
            is not MaterialCategory.PANORAMA
        ):
            return []

        return [
            RiskFinding(
                finding_id=(
                    f"{material_input.material.material_id}:"
                    "minor_shading:1"
                ),
                material_id=(
                    material_input.material.material_id
                ),
                category=(
                    RiskCategory.MINOR_SHADING
                ),
                label="轻微遮挡",
                detection_status=(
                    DetectionStatus.DETECTED
                ),
                severity=RiskSeverity.LOW,
                confidence=0.88,
                bbox=None,
                evidence_text=(
                    "组件表面存在小面积阴影"
                ),
                provider=self.name,
                model=self.model_name,
                requires_manual_review=False,
            )
        ]


class FailingOcrProvider(OcrProvider):
    @property
    def name(self) -> str:
        return "failing-ocr-provider"

    @property
    def model_name(self) -> str:
        return "failing-ocr-v1"

    def extract(
        self,
        material_input: MaterialInput,
    ) -> list[OcrField]:
        del material_input

        raise ProviderError(
            "sensitive upstream provider details"
        )


@pytest.fixture
def override_real_providers() -> Iterator[
    ProviderOverride
]:
    original_ocr_override = (
        app.dependency_overrides.get(
            get_ocr_provider
        )
    )
    original_vision_override = (
        app.dependency_overrides.get(
            get_vision_provider
        )
    )

    def apply_override(
        ocr_provider: OcrProvider,
        vision_provider: VisionProvider,
    ) -> None:
        app.dependency_overrides[
            get_ocr_provider
        ] = lambda: ocr_provider

        app.dependency_overrides[
            get_vision_provider
        ] = lambda: vision_provider

    yield apply_override

    if original_ocr_override is None:
        app.dependency_overrides.pop(
            get_ocr_provider,
            None,
        )
    else:
        app.dependency_overrides[
            get_ocr_provider
        ] = original_ocr_override

    if original_vision_override is None:
        app.dependency_overrides.pop(
            get_vision_provider,
            None,
        )
    else:
        app.dependency_overrides[
            get_vision_provider
        ] = original_vision_override


def test_runs_complete_real_underwriting_pipeline(
    override_real_providers: ProviderOverride,
) -> None:
    ocr_provider = RecordingOcrProvider()
    vision_provider = RecordingVisionProvider()

    override_real_providers(
        ocr_provider,
        vision_provider,
    )

    response = client.post(
        "/api/v1/underwriting/analyze",
        data={
            "manifest": json.dumps(
                manifest_payload(),
                ensure_ascii=False,
            )
        },
        files=[
            (
                "files",
                (
                    "component-nameplate.png",
                    png_bytes("white"),
                    "image/png",
                ),
            ),
            (
                "files",
                (
                    "site-panorama.png",
                    png_bytes("gray"),
                    "image/png",
                ),
            ),
        ],
    )

    assert response.status_code == 200

    result = response.json()

    assert (
        result["case_id"]
        == "case-real-api-001"
    )
    assert len(result["materials"]) == 2
    assert len(result["ocr_fields"]) == 1
    assert len(result["findings"]) == 1
    assert len(result["material_reviews"]) == 2
    assert len(result["processing_trace"]) == 4

    assert (
        result["ocr_fields"][0]["field_name"]
        == "component_model"
    )
    assert (
        result["findings"][0]["category"]
        == "minor_shading"
    )
    assert (
        result["decision"]["decision"]
        == "manual_review"
    )

    assert len(
        ocr_provider.received_inputs
    ) == 2
    assert len(
        vision_provider.received_inputs
    ) == 2

    assert (
        ocr_provider
        .received_inputs[0]
        .material
        .file_name
        == "component-nameplate.png"
    )
    assert (
        ocr_provider
        .received_inputs[1]
        .material
        .file_name
        == "site-panorama.png"
    )


def test_rejects_file_count_mismatch(
    override_real_providers: ProviderOverride,
) -> None:
    ocr_provider = RecordingOcrProvider()
    vision_provider = RecordingVisionProvider()

    override_real_providers(
        ocr_provider,
        vision_provider,
    )

    response = client.post(
        "/api/v1/underwriting/analyze",
        data={
            "manifest": json.dumps(
                manifest_payload(),
                ensure_ascii=False,
            )
        },
        files={
            "files": (
                "component-nameplate.png",
                png_bytes(),
                "image/png",
            )
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": {
            "message": (
                "Uploaded file count does not "
                "match manifest materials"
            ),
            "expected": 2,
            "received": 1,
        }
    }
    assert ocr_provider.received_inputs == []
    assert vision_provider.received_inputs == []


def test_rejects_invalid_manifest(
    override_real_providers: ProviderOverride,
) -> None:
    ocr_provider = RecordingOcrProvider()
    vision_provider = RecordingVisionProvider()

    override_real_providers(
        ocr_provider,
        vision_provider,
    )

    response = client.post(
        "/api/v1/underwriting/analyze",
        data={
            "manifest": "{not-valid-json"
        },
        files={
            "files": (
                "component-nameplate.png",
                png_bytes(),
                "image/png",
            )
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"][
        "message"
    ] == "Invalid underwriting manifest"
    assert ocr_provider.received_inputs == []
    assert vision_provider.received_inputs == []


def test_rejects_duplicate_uploaded_files(
    override_real_providers: ProviderOverride,
) -> None:
    ocr_provider = RecordingOcrProvider()
    vision_provider = RecordingVisionProvider()

    override_real_providers(
        ocr_provider,
        vision_provider,
    )

    duplicate_content = png_bytes()

    response = client.post(
        "/api/v1/underwriting/analyze",
        data={
            "manifest": json.dumps(
                manifest_payload(),
                ensure_ascii=False,
            )
        },
        files=[
            (
                "files",
                (
                    "component-nameplate.png",
                    duplicate_content,
                    "image/png",
                ),
            ),
            (
                "files",
                (
                    "site-panorama.png",
                    duplicate_content,
                    "image/png",
                ),
            ),
        ],
    )

    assert response.status_code == 422

    detail = response.json()["detail"]

    assert detail["message"] == (
        "Uploaded file was rejected"
    )
    assert detail["file_index"] == 2
    assert "duplicate_file" in detail["issues"]
    assert ocr_provider.received_inputs == []
    assert vision_provider.received_inputs == []


def test_accepts_pdf_for_ocr_processing(
    override_real_providers: ProviderOverride,
) -> None:
    ocr_provider = RecordingOcrProvider()
    vision_provider = RecordingVisionProvider()

    override_real_providers(
        ocr_provider,
        vision_provider,
    )

    content = pdf_bytes()

    manifest = {
        "case_id": "case-pdf-001",
        "project": project_payload(),
        "materials": [
            {
                "material_id": (
                    "material-filing-001"
                ),
                "category": (
                    "filing_certificate"
                ),
            }
        ],
    }

    response = client.post(
        "/api/v1/underwriting/analyze",
        data={
            "manifest": json.dumps(
                manifest,
                ensure_ascii=False,
            )
        },
        files={
            "files": (
                "filing.pdf",
                content,
                "application/pdf",
            )
        },
    )

    assert response.status_code == 200

    result = response.json()

    assert len(result["materials"]) == 1
    assert (
        result["materials"][0]["media_type"]
        == "application/pdf"
    )
    assert (
        result["materials"][0]["file_name"]
        == "filing.pdf"
    )

    assert len(
        ocr_provider.received_inputs
    ) == 1
    assert len(
        vision_provider.received_inputs
    ) == 1

    assert (
        ocr_provider
        .received_inputs[0]
        .material
        .media_type
        == "application/pdf"
    )
    assert (
        ocr_provider
        .received_inputs[0]
        .content
        == content
    )


def test_records_provider_failure_without_leaking_details(
    override_real_providers: ProviderOverride,
) -> None:
    vision_provider = RecordingVisionProvider()

    override_real_providers(
        FailingOcrProvider(),
        vision_provider,
    )

    manifest = {
        "case_id": "case-provider-failure-001",
        "project": project_payload(),
        "materials": [
            {
                "material_id": (
                    "material-panorama-001"
                ),
                "category": "panorama",
            }
        ],
    }

    response = client.post(
        "/api/v1/underwriting/analyze",
        data={
            "manifest": json.dumps(
                manifest,
                ensure_ascii=False,
            )
        },
        files={
            "files": (
                "site-panorama.png",
                png_bytes(),
                "image/png",
            )
        },
    )

    assert response.status_code == 200

    result = response.json()

    ocr_trace = next(
        trace
        for trace in result["processing_trace"]
        if trace["step"] == ProcessingStep.OCR
    )

    assert (
        ocr_trace["status"]
        == ProcessingStatus.FAILED
    )
    assert (
        ocr_trace["error_code"]
        == "OCR_PROVIDER_FAILURE"
    )
    assert (
        "sensitive upstream provider details"
        not in response.text
    )
    assert (
        "SYS-PROVIDER-FAILURE"
        in result["decision"]["decisive_rule_ids"]
    )
