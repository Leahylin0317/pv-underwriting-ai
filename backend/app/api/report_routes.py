from fastapi import APIRouter, Response

from app.contracts import UnderwritingCase
from app.reports import generate_markdown_report

router = APIRouter()


class MarkdownResponse(Response):
    media_type = "text/markdown"


@router.post(
    "/api/v1/reports/render",
    response_class=MarkdownResponse,
    tags=["reports"],
)
def render_underwriting_report(
    case: UnderwritingCase,
) -> MarkdownResponse:
    """把完整核保结果转换为可下载的 Markdown 报告。"""

    report = generate_markdown_report(
        case
    )

    return MarkdownResponse(
        content=report,
        headers={
            "Content-Disposition": (
                "attachment; "
                'filename="underwriting-report.md"'
            )
        },
    )
