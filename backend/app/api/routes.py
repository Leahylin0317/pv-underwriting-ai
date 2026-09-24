from fastapi import APIRouter

from app.contracts import UnderwritingCase
from app.pipeline import UnderwritingPipeline
from app.providers import MaterialInput, MockOcrProvider, MockVisionProvider

from .schemas import MockAnalyzeRequest

router = APIRouter()

_mock_pipeline = UnderwritingPipeline(
    ocr_provider=MockOcrProvider(),
    vision_provider=MockVisionProvider(),
)


@router.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """检查后端服务是否正常运行。"""

    return {"status": "ok"}


@router.post(
    "/api/v1/analyze/mock",
    response_model=UnderwritingCase,
    tags=["underwriting"],
)
def analyze_mock(request: MockAnalyzeRequest) -> UnderwritingCase:
    """使用 Mock Provider 执行一次完整核保流程。"""

    material_inputs = [
        MaterialInput(
            material=material,
            content=b"mock-file-content",
        )
        for material in request.materials
    ]

    return _mock_pipeline.run(
        case_id=request.case_id,
        project=request.project,
        materials=material_inputs,
    )
