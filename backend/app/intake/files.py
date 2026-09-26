from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Literal

import pymupdf
from PIL import Image, UnidentifiedImageError
from pydantic import Field

from app.contracts import ContractModel

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024
MAX_FILES_PER_REQUEST = 20


class FileInspectionResult(ContractModel):
    """上传文件的基础检查结果。"""

    file_name: str = Field(min_length=1)
    media_type: str | None
    size_bytes: int = Field(ge=0)
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    status: Literal["accepted", "rejected", "duplicate"]
    issues: list[str]
    page_count: int | None = Field(default=None, ge=1)
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)


def safe_file_name(file_name: str | None) -> str:
    """移除客户端文件名中的目录部分。"""

    normalized = Path(file_name or "unnamed").name
    return normalized or "unnamed"


def inspect_file(
    *,
    file_name: str | None,
    declared_media_type: str | None,
    content: bytes,
    seen_sha256: set[str] | None = None,
) -> FileInspectionResult:
    """检查单个上传文件，不保存文件内容。"""

    normalized_name = safe_file_name(file_name)
    size_bytes = len(content)

    if size_bytes == 0:
        return FileInspectionResult(
            file_name=normalized_name,
            media_type=None,
            size_bytes=0,
            sha256=None,
            status="rejected",
            issues=["empty_file"],
        )

    if size_bytes > MAX_FILE_SIZE_BYTES:
        return FileInspectionResult(
            file_name=normalized_name,
            media_type=None,
            size_bytes=size_bytes,
            sha256=None,
            status="rejected",
            issues=["file_too_large"],
        )

    digest = sha256(content).hexdigest()
    media_type, page_count, width, height, issues = inspect_content(content)

    if issues:
        return FileInspectionResult(
            file_name=normalized_name,
            media_type=media_type,
            size_bytes=size_bytes,
            sha256=digest,
            status="rejected",
            issues=issues,
            page_count=page_count,
            width=width,
            height=height,
        )

    accepted_issues: list[str] = []
    if declared_media_type and declared_media_type != media_type:
        accepted_issues.append("declared_media_type_mismatch")

    if seen_sha256 is not None and digest in seen_sha256:
        return FileInspectionResult(
            file_name=normalized_name,
            media_type=media_type,
            size_bytes=size_bytes,
            sha256=digest,
            status="duplicate",
            issues=[*accepted_issues, "duplicate_file"],
            page_count=page_count,
            width=width,
            height=height,
        )

    if seen_sha256 is not None:
        seen_sha256.add(digest)

    return FileInspectionResult(
        file_name=normalized_name,
        media_type=media_type,
        size_bytes=size_bytes,
        sha256=digest,
        status="accepted",
        issues=accepted_issues,
        page_count=page_count,
        width=width,
        height=height,
    )


def inspect_content(
    content: bytes,
) -> tuple[str | None, int | None, int | None, int | None, list[str]]:
    """根据真实文件内容判断格式和可打开性。"""

    if content.startswith(b"%PDF-"):
        return inspect_pdf(content)
    return inspect_image(content)


def inspect_pdf(
    content: bytes,
) -> tuple[str, int | None, None, None, list[str]]:
    """检查 PDF 是否可打开、是否加密以及是否包含页面。"""

    try:
        with pymupdf.open(stream=content, filetype="pdf") as document:
            if document.needs_pass:
                return "application/pdf", None, None, None, ["password_protected_pdf"]
            if document.page_count < 1:
                return "application/pdf", None, None, None, ["empty_pdf"]
            return "application/pdf", document.page_count, None, None, []
    except (OSError, RuntimeError, ValueError):
        return "application/pdf", None, None, None, ["corrupt_pdf"]


def inspect_image(
    content: bytes,
) -> tuple[str | None, None, int | None, int | None, list[str]]:
    """检查 JPEG 或 PNG 是否可打开并读取尺寸。"""

    try:
        with Image.open(BytesIO(content)) as image:
            image_format = image.format
            width, height = image.size
            image.verify()
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError):
        return None, None, None, None, ["unsupported_or_corrupt_file"]

    media_types = {
        "JPEG": "image/jpeg",
        "PNG": "image/png",
    }
    media_type = media_types.get(image_format or "")
    if media_type is None:
        return None, None, width, height, ["unsupported_image_format"]

    return media_type, None, width, height, []
