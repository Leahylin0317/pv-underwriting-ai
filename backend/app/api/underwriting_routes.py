from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from pydantic import ValidationError

from app.contracts import (
    Material,
    MaterialParseStatus,
    MaterialQualityStatus,
    UnderwritingCase,
)
from app.intake import (
    MAX_FILES_PER_REQUEST,
    inspect_file,
)
from app.pipeline import UnderwritingPipeline
from app.providers import (
    MaterialInput,
    OcrProvider,
    VisionProvider,
)
from app.providers.component import (
    ComponentProvider,
)

from .component_dependencies import (
    get_component_provider,
)
from .ocr_routes import get_ocr_provider
from .routes import get_vision_provider
from .schemas import RealAnalyzeManifest

router = APIRouter()

REAL_PIPELINE_MEDIA_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
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

    for uploaded_file in files:
        try:
            content = await uploaded_file.read()
        finally:
            await uploaded_file.close()

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
            file_name=inspection.file_name,
            media_type=inspection.media_type,
            sha256=inspection.sha256,
            quality_status=(
                MaterialQualityStatus.USABLE
            ),
            quality_confidence=None,
            quality_issues=inspection.issues,
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

    parsed_manifest = _parse_manifest(
        manifest
    )

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

    if (
        len(files)
        != len(parsed_manifest.materials)
    ):
        raise HTTPException(
            status_code=(
                status
                .HTTP_422_UNPROCESSABLE_CONTENT
            ),
            detail={
                "message": (
                    "Uploaded file count does not "
                    "match manifest materials"
                ),
                "expected": len(
                    parsed_manifest.materials
                ),
                "received": len(files),
            },
        )

    uploaded_files = await _read_uploaded_files(
        files
    )

    material_inputs = _build_material_inputs(
        manifest=parsed_manifest,
        uploaded_files=uploaded_files,
    )

    pipeline = UnderwritingPipeline(
        ocr_provider=ocr_provider,
        vision_provider=vision_provider,
        component_provider=(
            component_provider
        ),
    )

    return pipeline.run(
        case_id=parsed_manifest.case_id,
        project=parsed_manifest.project,
        materials=material_inputs,
    )
