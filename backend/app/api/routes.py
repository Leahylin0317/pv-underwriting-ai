from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    status,
)

from app.contracts import (
    Material,
    MaterialCategory,
    MaterialParseStatus,
    MaterialQualityStatus,
    RiskFinding,
    UnderwritingCase,
)
from app.intake import (
    MAX_FILES_PER_REQUEST,
    FileInspectionResult,
    inspect_file,
)
from app.pipeline import UnderwritingPipeline
from app.providers import (
    CompatibleVisionProvider,
    MaterialInput,
    MockOcrProvider,
    MockVisionProvider,
    ProviderError,
    VisionProvider,
)
from app.reports import generate_markdown_report
from app.settings import (
    ProviderConfigurationError,
    VlmSettings,
)

from .schemas import MockAnalyzeRequest

router = APIRouter()

VISION_MEDIA_TYPES = {
    "image/jpeg",
    "image/png",
}

_mock_pipeline = UnderwritingPipeline(
    ocr_provider=MockOcrProvider(),
    vision_provider=MockVisionProvider(),
)


class MarkdownResponse(Response):
    media_type = "text/markdown"


def get_vision_provider() -> VisionProvider:
    """根据本地环境配置创建真实视觉模型 Provider。"""

    try:
        settings = VlmSettings.from_environment()
    except ProviderConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vision provider is not configured",
        ) from exc

    return CompatibleVisionProvider(
        settings=settings,
    )


def _run_mock_analysis(
    request: MockAnalyzeRequest,
) -> UnderwritingCase:
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


@router.get(
    "/health",
    tags=["system"],
)
def health_check() -> dict[str, str]:
    """检查后端服务是否正常运行。"""

    return {"status": "ok"}


@router.post(
    "/api/v1/files/inspect",
    response_model=list[FileInspectionResult],
    tags=["materials"],
)
async def inspect_uploaded_files(
    files: Annotated[
        list[UploadFile],
        File(
            description=(
                "需要检查的 JPEG、PNG 或 PDF 文件"
            )
        ),
    ],
) -> list[FileInspectionResult]:
    """检查上传文件的格式、可读性、大小和重复情况。"""

    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(
            status_code=(
                status.HTTP_413_CONTENT_TOO_LARGE
            ),
            detail=(
                f"A maximum of "
                f"{MAX_FILES_PER_REQUEST} "
                "files is allowed"
            ),
        )

    seen_sha256: set[str] = set()
    results: list[FileInspectionResult] = []

    for uploaded_file in files:
        try:
            content = await uploaded_file.read()
        finally:
            await uploaded_file.close()

        results.append(
            inspect_file(
                file_name=uploaded_file.filename,
                declared_media_type=(
                    uploaded_file.content_type
                ),
                content=content,
                seen_sha256=seen_sha256,
            )
        )

    return results


@router.post(
    "/api/v1/vision/analyze",
    response_model=list[RiskFinding],
    tags=["vision"],
)
async def analyze_uploaded_image(
    vision_provider: Annotated[
        VisionProvider,
        Depends(get_vision_provider),
    ],
    file: Annotated[
        UploadFile,
        File(
            description=(
                "需要进行风险识别的 JPEG 或 PNG 图片"
            )
        ),
    ],
    material_id: Annotated[
        str,
        Form(
            min_length=1,
            description="材料唯一编号",
        ),
    ] = "material-upload-001",
    category: Annotated[
        MaterialCategory,
        Form(
            description="材料类别",
        ),
    ] = MaterialCategory.PANORAMA,
) -> list[RiskFinding]:
    """检查上传图片并调用真实视觉模型识别风险。"""

    try:
        content = await file.read()
    finally:
        await file.close()

    inspection = inspect_file(
        file_name=file.filename,
        declared_media_type=file.content_type,
        content=content,
    )

    if inspection.status != "accepted":
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_CONTENT
            ),
            detail={
                "message": "Uploaded file was rejected",
                "issues": inspection.issues,
            },
        )

    if (
        inspection.media_type
        not in VISION_MEDIA_TYPES
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
            ),
            detail=(
                "Vision analysis supports only "
                "JPEG and PNG images"
            ),
        )

    if (
        inspection.media_type is None
        or inspection.sha256 is None
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_CONTENT
            ),
            detail="Uploaded image could not be inspected",
        )

    material = Material(
        material_id=material_id,
        category=category,
        file_name=inspection.file_name,
        media_type=inspection.media_type,
        sha256=inspection.sha256,
        quality_status=(
            MaterialQualityStatus.UNKNOWN
        ),
        quality_confidence=None,
        quality_issues=inspection.issues,
        parse_status=(
            MaterialParseStatus.SUCCESS
        ),
    )

    material_input = MaterialInput(
        material=material,
        content=content,
    )

    try:
        return vision_provider.analyze(
            material_input
        )
    except ProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Vision provider request failed",
        ) from exc


@router.post(
    "/api/v1/analyze/mock",
    response_model=UnderwritingCase,
    tags=["underwriting"],
)
def analyze_mock(
    request: MockAnalyzeRequest,
) -> UnderwritingCase:
    """使用 Mock Provider 执行一次完整核保流程。"""

    return _run_mock_analysis(request)


@router.post(
    "/api/v1/reports/mock",
    response_class=MarkdownResponse,
    tags=["reports"],
)
def download_mock_report(
    request: MockAnalyzeRequest,
) -> MarkdownResponse:
    """执行 Mock 核保流程并返回可下载的 Markdown 报告。"""

    case = _run_mock_analysis(request)
    report = generate_markdown_report(case)

    return MarkdownResponse(
        content=report,
        headers={
            "Content-Disposition": (
                'attachment; '
                'filename="underwriting-report.md"'
            )
        },
    )
