from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Response, UploadFile, status

from app.contracts import UnderwritingCase
from app.intake import MAX_FILES_PER_REQUEST, FileInspectionResult, inspect_file
from app.pipeline import UnderwritingPipeline
from app.providers import MaterialInput, MockOcrProvider, MockVisionProvider
from app.reports import generate_markdown_report

from .schemas import MockAnalyzeRequest

router = APIRouter()

_mock_pipeline = UnderwritingPipeline(
    ocr_provider=MockOcrProvider(),
    vision_provider=MockVisionProvider(),
)


class MarkdownResponse(Response):
    media_type = "text/markdown"


def _run_mock_analysis(request: MockAnalyzeRequest) -> UnderwritingCase:
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


@router.get("/health", tags=["system"])
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
        File(description="需要检查的 JPEG、PNG 或 PDF 文件"),
    ],
) -> list[FileInspectionResult]:
    """检查上传文件的格式、可读性、大小和重复情况。"""

    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"A maximum of {MAX_FILES_PER_REQUEST} files is allowed",
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
                declared_media_type=uploaded_file.content_type,
                content=content,
                seen_sha256=seen_sha256,
            )
        )

    return results


@router.post(
    "/api/v1/analyze/mock",
    response_model=UnderwritingCase,
    tags=["underwriting"],
)
def analyze_mock(request: MockAnalyzeRequest) -> UnderwritingCase:
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
                'attachment; filename="underwriting-report.md"'
            )
        },
    )
