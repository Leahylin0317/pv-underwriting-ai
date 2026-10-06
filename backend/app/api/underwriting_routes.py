import logging
from threading import BoundedSemaphore
from typing import Annotated
from uuid import uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from app.catastrophe import CatastropheAssessmentEngine
from app.contracts import (
    Material,
    MaterialParseStatus,
    MaterialQualityStatus,
    ProjectInfo,
    UnderwritingCase,
)
from app.intake import (
    MAX_FILE_SIZE_BYTES,
    MAX_FILES_PER_REQUEST,
    MAX_TOTAL_UPLOAD_SIZE_BYTES,
    inspect_file,
    read_upload_limited,
)
from app.location import AmapGeocoder
from app.pipeline import UnderwritingPipeline
from app.providers import (
    MaterialInput,
    OcrProvider,
    VisionProvider,
    WeatherProvider,
)
from app.providers.component import (
    ComponentProvider,
)
from app.storage import (
    AnalysisJobRepository,
    CaseRepository,
    CaseRepositoryConflict,
)

from .component_dependencies import (
    get_component_provider,
)
from .ocr_routes import get_ocr_provider
from .routes import get_vision_provider
from .schemas import RealAnalyzeManifest
from .weather_dependencies import get_weather_provider

router = APIRouter()
_JOB_SLOTS = BoundedSemaphore(value=2)
logger = logging.getLogger(__name__)

REAL_PIPELINE_MEDIA_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _validation_error_summary(
    error: ValidationError,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []

    for item in error.errors(
        include_url=False,
        include_context=False,
        include_input=False,
    )[:10]:
        location = ".".join(
            str(part)
            for part in item["loc"]
        )

        issues.append(
            {
                "location": (
                    location or "manifest"
                ),
                "type": item["type"],
            }
        )

    return issues


def _parse_manifest(
    manifest: str,
) -> RealAnalyzeManifest:
    try:
        return (
            RealAnalyzeManifest
            .model_validate_json(manifest)
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=(
                status
                .HTTP_422_UNPROCESSABLE_CONTENT
            ),
            detail={
                "message": (
                    "Invalid underwriting manifest"
                ),
                "issues": (
                    _validation_error_summary(exc)
                ),
            },
        ) from exc


async def _read_uploaded_files(
    files: list[UploadFile],
) -> list[
    tuple[str | None, str | None, bytes]
]:
    payloads: list[
        tuple[str | None, str | None, bytes]
    ] = []
    total_bytes = 0

    for uploaded_file in files:
        try:
            content = await read_upload_limited(uploaded_file)
        finally:
            await uploaded_file.close()

        if len(content) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail={
                    "message": "Uploaded file exceeds the per-file size limit",
                    "file_name": uploaded_file.filename,
                    "maximum_bytes": MAX_FILE_SIZE_BYTES,
                },
            )

        total_bytes += len(content)
        if total_bytes > MAX_TOTAL_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail={
                    "message": "Total uploaded files exceed the request size limit",
                    "maximum_bytes": MAX_TOTAL_UPLOAD_SIZE_BYTES,
                },
            )

        payloads.append(
            (
                uploaded_file.filename,
                uploaded_file.content_type,
                content,
            )
        )

    return payloads


def _build_material_inputs(
    *,
    manifest: RealAnalyzeManifest,
    uploaded_files: list[
        tuple[str | None, str | None, bytes]
    ],
) -> list[MaterialInput]:
    seen_sha256: set[str] = set()
    material_inputs: list[
        MaterialInput
    ] = []

    for index, (
        material_manifest,
        uploaded_file,
    ) in enumerate(
        zip(
            manifest.materials,
            uploaded_files,
            strict=True,
        ),
        start=1,
    ):
        (
            file_name,
            declared_media_type,
            content,
        ) = uploaded_file

        inspection = inspect_file(
            file_name=file_name,
            declared_media_type=(
                declared_media_type
            ),
            content=content,
            seen_sha256=seen_sha256,
        )

        if inspection.status != "accepted":
            raise HTTPException(
                status_code=(
                    status
                    .HTTP_422_UNPROCESSABLE_CONTENT
                ),
                detail={
                    "message": (
                        "Uploaded file was rejected"
                    ),
                    "file_index": index,
                    "file_name": (
                        inspection.file_name
                    ),
                    "issues": inspection.issues,
                },
            )

        if (
            inspection.media_type
            not in REAL_PIPELINE_MEDIA_TYPES
        ):
            raise HTTPException(
                status_code=(
                    status
                    .HTTP_415_UNSUPPORTED_MEDIA_TYPE
                ),
                detail={
                    "message": (
                        "Real underwriting currently "
                        "supports only JPEG, PNG and "
                        "PDF files"
                    ),
                    "file_index": index,
                    "file_name": (
                        inspection.file_name
                    ),
                },
            )

        if (
            inspection.media_type is None
            or inspection.sha256 is None
        ):
            raise HTTPException(
                status_code=(
                    status
                    .HTTP_422_UNPROCESSABLE_CONTENT
                ),
                detail={
                    "message": (
                        "Uploaded material could not "
                        "be inspected"
                    ),
                    "file_index": index,
                    "file_name": (
                        inspection.file_name
                    ),
                },
            )

        material = Material(
            material_id=(
                material_manifest.material_id
            ),
            category=(
                material_manifest.category
            ),
            capture_view=material_manifest.capture_view,
            file_name=inspection.file_name,
            media_type=inspection.media_type,
            sha256=inspection.sha256,
            quality_status=(
                inspection.quality_status
                or MaterialQualityStatus.USABLE
            ),
            quality_confidence=None,
            quality_issues=inspection.quality_issues,
            parse_status=(
                MaterialParseStatus.SUCCESS
            ),
        )

        material_inputs.append(
            MaterialInput(
                material=material,
                content=content,
            )
        )

    return material_inputs


async def _prepare_uploaded_case(
    *,
    manifest: str,
    files: list[UploadFile],
) -> tuple[RealAnalyzeManifest, list[MaterialInput]]:
    parsed_manifest = _parse_manifest(manifest)
    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"A maximum of {MAX_FILES_PER_REQUEST} files is allowed",
        )
    if len(files) != len(parsed_manifest.materials):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "message": "Uploaded file count does not match manifest materials",
                "expected": len(parsed_manifest.materials),
                "received": len(files),
            },
        )
    uploaded_files = await _read_uploaded_files(files)
    material_inputs = _build_material_inputs(
        manifest=parsed_manifest,
        uploaded_files=uploaded_files,
    )
    return parsed_manifest, material_inputs


def _run_analysis_job(
    *,
    job_id: str,
    case_id: str,
    project: ProjectInfo,
    materials: list[MaterialInput],
    ocr_provider: OcrProvider,
    vision_provider: VisionProvider,
    component_provider: ComponentProvider,
    weather_provider: WeatherProvider,
) -> None:
    jobs = AnalysisJobRepository()
    def report_progress(step: str, progress_percent: int) -> None:
        jobs.update_job(
            job_id,
            status="running",
            progress_percent=progress_percent,
            current_step=step,
        )

    try:
        jobs.update_job(
            job_id,
            status="running",
            progress_percent=1,
            current_step="开始核保分析",
        )
        pipeline = UnderwritingPipeline(
            ocr_provider=ocr_provider,
            vision_provider=vision_provider,
            component_provider=component_provider,
            weather_provider=weather_provider,
            catastrophe_engine=CatastropheAssessmentEngine(),
            location_geocoder=AmapGeocoder.from_environment(),
            progress_callback=report_progress,
        )
        case = pipeline.run(
            case_id=case_id,
            project=project,
            materials=materials,
        )
        CaseRepository().save_case(case)
        jobs.update_job(
            job_id,
            status="completed",
            progress_percent=100,
            current_step="核保分析完成",
            result=case,
        )
    except CaseRepositoryConflict:
        jobs.update_job(
            job_id,
            status="failed",
            progress_percent=100,
            current_step="案件编号已使用",
            error_code="CASE_ID_EXISTS",
        )
    except Exception as exc:  # noqa: BLE001 - keep the background task status terminal
        logger.error(
            "underwriting analysis job failed: job_id=%s error_type=%s",
            job_id,
            type(exc).__name__,
        )
        jobs.update_job(
            job_id,
            status="failed",
            progress_percent=100,
            current_step="核保分析失败，请检查服务配置或处理记录",
            error_code="ANALYSIS_FAILED",
        )
    finally:
        _JOB_SLOTS.release()


@router.post(
    "/api/v1/underwriting/analyze",
    response_model=UnderwritingCase,
    tags=["underwriting"],
)
async def analyze_uploaded_case(
    ocr_provider: Annotated[
        OcrProvider,
        Depends(get_ocr_provider),
    ],
    vision_provider: Annotated[
        VisionProvider,
        Depends(get_vision_provider),
    ],
    component_provider: Annotated[
        ComponentProvider,
        Depends(get_component_provider),
    ],
    weather_provider: Annotated[
        WeatherProvider,
        Depends(get_weather_provider),
    ],
    files: Annotated[
        list[UploadFile],
        File(
            description=(
                "投保材料文件，顺序必须与 "
                "manifest.materials 保持一致"
            )
        ),
    ],
    manifest: Annotated[
        str,
        Form(
            description=(
                "案件、项目信息和材料清单组成的 "
                "JSON 字符串"
            )
        ),
    ],
) -> UnderwritingCase:
    """使用真实模型和组件目录执行完整核保流水线。"""

    parsed_manifest, material_inputs = await _prepare_uploaded_case(
        manifest=manifest,
        files=files,
    )

    pipeline = UnderwritingPipeline(
        ocr_provider=ocr_provider,
        vision_provider=vision_provider,
        component_provider=(
            component_provider
        ),
        weather_provider=weather_provider,
        catastrophe_engine=(
            CatastropheAssessmentEngine()
        ),
    )

    case = await run_in_threadpool(
        pipeline.run,
        case_id=parsed_manifest.case_id,
        project=parsed_manifest.project,
        materials=material_inputs,
    )
    try:
        await run_in_threadpool(CaseRepository().save_case, case)
    except CaseRepositoryConflict as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This case ID already has a saved analysis. "
                "Use a new case ID to create another run."
            ),
        ) from exc
    return case


@router.post(
    "/api/v1/underwriting/jobs",
    status_code=status.HTTP_202_ACCEPTED,
    tags=["underwriting"],
)
async def submit_underwriting_job(
    background_tasks: BackgroundTasks,
    ocr_provider: Annotated[OcrProvider, Depends(get_ocr_provider)],
    vision_provider: Annotated[VisionProvider, Depends(get_vision_provider)],
    component_provider: Annotated[ComponentProvider, Depends(get_component_provider)],
    weather_provider: Annotated[WeatherProvider, Depends(get_weather_provider)],
    files: Annotated[list[UploadFile], File()],
    manifest: Annotated[str, Form()],
) -> dict[str, str]:
    """Queue a local analysis and return a job identifier for progress polling."""

    if not _JOB_SLOTS.acquire(blocking=False):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The local analysis queue is at capacity; retry shortly.",
        )

    job_id = uuid4().hex
    try:
        parsed_manifest, material_inputs = await _prepare_uploaded_case(
            manifest=manifest,
            files=files,
        )
        await run_in_threadpool(
            AnalysisJobRepository().create_job,
            job_id,
            parsed_manifest.case_id,
        )
        background_tasks.add_task(
            _run_analysis_job,
            job_id=job_id,
            case_id=parsed_manifest.case_id,
            project=parsed_manifest.project,
            materials=material_inputs,
            ocr_provider=ocr_provider,
            vision_provider=vision_provider,
            component_provider=component_provider,
            weather_provider=weather_provider,
        )
    except Exception:
        _JOB_SLOTS.release()
        raise

    return {"job_id": job_id, "status": "queued"}


@router.get("/api/v1/underwriting/jobs/{job_id}")
async def get_underwriting_job(job_id: str) -> dict[str, object]:
    """Return the current status, progress and completed case result, if ready."""

    job = await run_in_threadpool(AnalysisJobRepository().get_job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job
