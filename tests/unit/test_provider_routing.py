from dataclasses import replace
import pytest
from app.contracts import (
    Material,
    MaterialCategory,
    MaterialParseStatus,
    MaterialQualityStatus,
    OcrField,
    RiskFinding,
    WatermarkStatus,
)
from app.providers import MaterialInput
from app.providers.ocr.base import OcrProvider
from app.providers.routing import (
    RoutedOcrProvider,
    RoutedVisionProvider,
    should_run_ocr,
    should_run_vision,
)
from app.providers.vision.base import VisionProvider


def make_material_input(
    category: MaterialCategory,
    *,
    media_type: str = "image/png",
) -> MaterialInput:
    material = Material(
        material_id=(
            f"material-{category.value}"
        ),
        category=category,
        file_name="material.png",
        media_type=media_type,
        quality_status=(
            MaterialQualityStatus.USABLE
        ),
        quality_confidence=0.95,
        quality_issues=[],
        parse_status=(
            MaterialParseStatus.SUCCESS
        ),
    )

    return MaterialInput(
        material=material,
        content=b"material-content",
    )


class RecordingOcrProvider(OcrProvider):
    def __init__(self) -> None:
        self.received_inputs: list[
            MaterialInput
        ] = []

    @property
    def name(self) -> str:
        return "recording-ocr"

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
        return []


class RecordingVisionProvider(VisionProvider):
    def __init__(self) -> None:
        self.received_inputs: list[
            MaterialInput
        ] = []

    @property
    def name(self) -> str:
        return "recording-vision"

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
        return []


@pytest.mark.parametrize(
    ("category", "expected"),
    [
        (
            MaterialCategory.FILING_CERTIFICATE,
            True,
        ),
        (
            MaterialCategory.GRID_CONNECTION_DOCUMENT,
            True,
        ),
        (
            MaterialCategory.ELECTRICAL_GROUNDING,
            True,
        ),
        (
            MaterialCategory.COMPONENT_NAMEPLATE,
            True,
        ),
        (
            MaterialCategory.INVERTER_NAMEPLATE,
            True,
        ),
        (
            MaterialCategory.COMBINER_BOX,
            True,
        ),
        (
            MaterialCategory.MONITORING_OPTIONAL,
            True,
        ),
        (
            MaterialCategory.OTHER,
            True,
        ),
        (
            MaterialCategory.PANORAMA,
            True,
        ),
        (
            MaterialCategory.ROOF_CONNECTION,
            False,
        ),
        (
            MaterialCategory.PARAPET,
            False,
        ),
        (
            MaterialCategory.WORKSHOP,
            False,
        ),
    ],
)
def test_ocr_category_routing(
    category: MaterialCategory,
    expected: bool,
) -> None:
    material_input = make_material_input(
        category
    )

    assert (
        should_run_ocr(material_input)
        is expected
    )


@pytest.mark.parametrize(
    ("category", "expected"),
    [
        (
            MaterialCategory.PANORAMA,
            True,
        ),
        (
            MaterialCategory.ROOF_CONNECTION,
            True,
        ),
        (
            MaterialCategory.PARAPET,
            True,
        ),
        (
            MaterialCategory.WORKSHOP,
            True,
        ),
        (
            MaterialCategory.ELECTRICAL_GROUNDING,
            True,
        ),
        (
            MaterialCategory.COMBINER_BOX,
            True,
        ),
        (
            MaterialCategory.MONITORING_OPTIONAL,
            True,
        ),
        (
            MaterialCategory.OTHER,
            True,
        ),
        (
            MaterialCategory.FILING_CERTIFICATE,
            False,
        ),
        (
            MaterialCategory.GRID_CONNECTION_DOCUMENT,
            False,
        ),
        (
            MaterialCategory.COMPONENT_NAMEPLATE,
            True,
        ),
        (
            MaterialCategory.INVERTER_NAMEPLATE,
            True,
        ),
    ],
)
def test_vision_category_routing(
    category: MaterialCategory,
    expected: bool,
) -> None:
    material_input = make_material_input(
        category
    )

    assert (
        should_run_vision(material_input)
        is expected
    )


def test_pdf_is_not_sent_to_vision() -> None:
    material_input = make_material_input(
        MaterialCategory.OTHER,
        media_type="application/pdf",
    )

    assert should_run_ocr(material_input)
    assert not should_run_vision(
        material_input
    )


def test_routed_ocr_provider_calls_panorama_for_watermark_ocr() -> None:
    delegate = RecordingOcrProvider()
    provider = RoutedOcrProvider(delegate)
    material_input = make_material_input(
        MaterialCategory.PANORAMA
    )
    material_input.material.watermark_status = WatermarkStatus.PRESENT

    provider.extract(material_input)

    assert delegate.received_inputs == [replace(material_input, ocr_task="watermark")]


def test_routed_ocr_skips_panorama_when_vision_confirms_no_watermark() -> None:
    delegate = RecordingOcrProvider()
    provider = RoutedOcrProvider(delegate)
    material_input = make_material_input(MaterialCategory.PANORAMA)
    material_input.material.watermark_status = WatermarkStatus.ABSENT

    provider.extract(material_input)

    assert delegate.received_inputs == []


def test_routed_ocr_provider_calls_delegate() -> None:
    delegate = RecordingOcrProvider()
    provider = RoutedOcrProvider(delegate)

    material_input = make_material_input(
        MaterialCategory.COMPONENT_NAMEPLATE
    )

    provider.extract(material_input)

    assert delegate.received_inputs == [replace(material_input, ocr_task="business")]


def test_routed_vision_provider_skips_document() -> None:
    delegate = RecordingVisionProvider()
    provider = RoutedVisionProvider(delegate)

    provider.analyze(
        make_material_input(
            MaterialCategory.FILING_CERTIFICATE
        )
    )

    assert delegate.received_inputs == []


def test_routed_vision_provider_calls_delegate() -> None:
    delegate = RecordingVisionProvider()
    provider = RoutedVisionProvider(delegate)

    material_input = make_material_input(
        MaterialCategory.PANORAMA
    )

    provider.analyze(material_input)

    assert delegate.received_inputs == [
        material_input
    ]

@pytest.mark.parametrize('category,status,tasks', [
    (MaterialCategory.WORKSHOP, WatermarkStatus.PRESENT, ['watermark']),
    (MaterialCategory.WORKSHOP, WatermarkStatus.UNCERTAIN, ['watermark']),
    (MaterialCategory.WORKSHOP, WatermarkStatus.ABSENT, []),
    (MaterialCategory.COMPONENT_NAMEPLATE, WatermarkStatus.PRESENT, ['watermark','business']),
    (MaterialCategory.COMPONENT_NAMEPLATE, WatermarkStatus.ABSENT, ['business']),
    (MaterialCategory.PROJECT_DOCUMENT, WatermarkStatus.PRESENT, ['business']),
])
def test_independent_extraction_routes(category, status, tasks):
    from app.providers.ocr.tasks import extract_tasks
    provider = RecordingOcrProvider()
    source = make_material_input(category)
    source.material.watermark_status = status
    _, details = extract_tasks(provider, source)
    assert [x.ocr_task for x in provider.received_inputs] == tasks
    assert [x['task'] for x in details if x['status']=='success'] == tasks

@pytest.mark.parametrize('failed_task', ['watermark','business'])
def test_extraction_failure_preserves_other_task(failed_task):
    from app.providers.common import ProviderError
    from app.providers.ocr.tasks import extract_tasks
    class PartialProvider(RecordingOcrProvider):
        def extract(self, source):
            if source.ocr_task == failed_task:
                raise ProviderError('upstream failure')
            return [OcrField(field_id='field', material_id=source.material.material_id,
                             field_name='watermark_date' if source.ocr_task=='watermark' else 'component_model',
                             raw_value='visible', normalized_value='visible', confidence=0.9,
                             value_status='extracted', evidence_text='visible text', provider='test', model='test')]
    source = make_material_input(MaterialCategory.COMPONENT_NAMEPLATE)
    source.material.watermark_status = WatermarkStatus.PRESENT
    fields, details = extract_tasks(PartialProvider(), source)
    assert len(fields)==1
    assert fields[0].extraction_task != failed_task
    assert next(x for x in details if x['task']==failed_task)['status']=='failed'
    assert next(x for x in details if x['task']!=failed_task)['status']=='success'
