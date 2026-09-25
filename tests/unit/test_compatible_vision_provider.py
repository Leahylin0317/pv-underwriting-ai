import json

import httpx
import pytest
from app.contracts import (
    DetectionStatus,
    Material,
    MaterialCategory,
    MaterialParseStatus,
    MaterialQualityStatus,
)
from app.providers import (
    CompatibleVisionProvider,
    MaterialInput,
    ProviderError,
)
from app.settings import VlmSettings


def make_material_input(
    *,
    media_type: str = "image/png",
    content: bytes = b"image-bytes",
) -> MaterialInput:
    material = Material(
        material_id="material-panorama-001",
        category=MaterialCategory.PANORAMA,
        file_name="panorama.png",
        media_type=media_type,
        quality_status=MaterialQualityStatus.USABLE,
        quality_confidence=0.95,
        quality_issues=[],
        parse_status=MaterialParseStatus.SUCCESS,
    )

    return MaterialInput(
        material=material,
        content=content,
    )


def make_settings() -> VlmSettings:
    return VlmSettings(
        base_url="https://api.example.com/v1",
        api_key="secret-test-key",
        model="example-vision-model",
        timeout_seconds=10,
    )


def successful_response_content() -> str:
    return """```json
{
  "findings": [
    {
      "category": "water_adjacent_environment",
      "label": "临近水体",
      "detection_status": "detected",
      "severity": "high",
      "confidence": 0.86,
      "bbox": {
        "x_min": 0.5,
        "y_min": 0.1,
        "x_max": 0.9,
        "y_max": 0.8,
        "coordinate_space": "normalized_0_1"
      },
      "evidence_text": "图片右侧存在大面积水体",
      "requires_manual_review": false
    },
    {
      "category": "severe_shading",
      "label": "疑似严重遮挡",
      "detection_status": "detected",
      "severity": "medium",
      "confidence": 0.4,
      "bbox": null,
      "evidence_text": "组件区域存在疑似阴影",
      "requires_manual_review": false
    },
    {
      "category": "hazardous_material",
      "label": "危险品",
      "detection_status": "not_detected",
      "severity": "info",
      "confidence": 0.9,
      "bbox": null,
      "evidence_text": "未发现危险品",
      "requires_manual_review": false
    }
  ]
}
```"""


def test_calls_compatible_api_and_converts_findings() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert str(request.url) == (
            "https://api.example.com/v1/"
            "chat/completions"
        )

        assert request.headers["Authorization"] == (
            "Bearer secret-test-key"
        )

        request_body = json.loads(request.content)

        assert request_body["model"] == (
            "example-vision-model"
        )

        image_url = request_body[
            "messages"
        ][1]["content"][1]["image_url"]["url"]

        assert image_url == (
            "data:image/png;base64,"
            "aW1hZ2UtYnl0ZXM="
        )

        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                successful_response_content()
                            ),
                        }
                    }
                ]
            },
        )

    provider = CompatibleVisionProvider(
        make_settings(),
        transport=httpx.MockTransport(handler),
    )

    findings = provider.analyze(
        make_material_input()
    )

    assert len(findings) == 2

    assert findings[0].finding_id == (
        "material-panorama-001:"
        "water_adjacent_environment:1"
    )

    assert findings[0].provider == (
        "openai-compatible-vision"
    )

    assert findings[0].model == (
        "example-vision-model"
    )

    assert findings[0].bbox is not None

    assert (
        findings[1].detection_status
        is DetectionStatus.UNCERTAIN
    )

    assert (
        findings[1].requires_manual_review
        is True
    )


def test_skips_non_image_material_without_calling_api() -> None:
    def handler(
        _request: httpx.Request,
    ) -> httpx.Response:
        pytest.fail(
            "API must not be called "
            "for non-image material"
        )

    provider = CompatibleVisionProvider(
        make_settings(),
        transport=httpx.MockTransport(handler),
    )

    findings = provider.analyze(
        make_material_input(
            media_type="application/pdf",
            content=b"pdf-bytes",
        )
    )

    assert findings == []


def test_rejects_empty_image() -> None:
    provider = CompatibleVisionProvider(
        make_settings()
    )

    with pytest.raises(
        ProviderError,
        match="received an empty image",
    ):
        provider.analyze(
            make_material_input(content=b"")
        )


def test_sanitizes_http_error() -> None:
    def handler(
        _request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            401,
            text="sensitive upstream error",
        )

    provider = CompatibleVisionProvider(
        make_settings(),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(
        ProviderError,
        match="returned HTTP 401",
    ) as exc_info:
        provider.analyze(
            make_material_input()
        )

    assert (
        "sensitive upstream error"
        not in str(exc_info.value)
    )

    assert (
        "secret-test-key"
        not in str(exc_info.value)
    )


def test_rejects_invalid_model_response() -> None:
    def handler(
        _request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "not-json"
                        }
                    }
                ]
            },
        )

    provider = CompatibleVisionProvider(
        make_settings(),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(
        ProviderError,
        match="returned an invalid response",
    ):
        provider.analyze(
            make_material_input()
        )


def test_rejects_invalid_confidence_threshold() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "confidence_threshold must be "
            "between zero and one"
        ),
    ):
        CompatibleVisionProvider(
            make_settings(),
            confidence_threshold=1.1,
        )
