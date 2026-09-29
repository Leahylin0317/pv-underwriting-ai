from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Response, status
from starlette.concurrency import run_in_threadpool

from app.contracts import DecisionType, UnderwritingCase
from app.reports import generate_markdown_report
from app.rules.explanations import explain_rules
from app.storage import CaseRepository

from .schemas import HumanReviewSubmission

router = APIRouter(prefix="/api/v1/cases", tags=["cases"])


def _include_legacy_rule_explanations(
    record: dict[str, object],
) -> dict[str, object]:
    """Backfill readable explanations when returning cases saved before the field existed."""
    case_payload = record.get("case")
    if not isinstance(case_payload, dict):
        return record
    decision_payload = case_payload.get("decision")
    if not isinstance(decision_payload, dict):
        return record
    rule_ids = decision_payload.get("decisive_rule_ids")
    if not isinstance(rule_ids, list) or not rule_ids:
        return record
    if decision_payload.get("rule_explanations"):
        return record
    decision_payload["rule_explanations"] = [
        item.model_dump(mode="json")
        for item in explain_rules([str(rule_id) for rule_id in rule_ids])
    ]
    return record


class MarkdownResponse(Response):
    media_type = "text/markdown"


@router.get("")
async def list_saved_cases(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    decision: DecisionType | None = None,
    review_status: Literal["pending", "completed"] | None = None,
) -> list[dict[str, object]]:
    """List saved case summaries, newest first."""

    return await run_in_threadpool(
        CaseRepository().list_cases,
        limit=limit,
        offset=offset,
        decision=decision.value if decision else None,
        review_status=review_status,
    )


@router.get("/{case_id}")
async def get_saved_case(case_id: str) -> dict[str, object]:
    """Return a saved case and its append-only human-review history."""

    result = await run_in_threadpool(CaseRepository().get_case, case_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return _include_legacy_rule_explanations(result)


@router.post("/{case_id}/review")
async def submit_human_review(
    case_id: str,
    submission: HumanReviewSubmission,
) -> dict[str, object]:
    """Record an authorized reviewer's final underwriting outcome."""

    result = await run_in_threadpool(
        CaseRepository().submit_review,
        case_id=case_id,
        reviewer_name=submission.reviewer_name.strip(),
        final_decision=submission.final_decision.value,
        comment=submission.comment.strip(),
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return _include_legacy_rule_explanations(result)


@router.get("/{case_id}/report", response_class=MarkdownResponse)
async def download_saved_case_report(case_id: str) -> MarkdownResponse:
    """Download the case report with both automated and human decisions."""

    record = await run_in_threadpool(CaseRepository().get_case, case_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    case = UnderwritingCase.model_validate(record["case"])
    report = generate_markdown_report(
        case,
        human_reviews=record["review_history"],
    )
    return MarkdownResponse(
        content=report,
        headers={
            "Content-Disposition": 'attachment; filename="underwriting-report.md"'
        },
    )
