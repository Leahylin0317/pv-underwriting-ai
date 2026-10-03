"""Online leads to manufacturer specifications, without automatic risk decisions."""

import os
from dataclasses import asdict

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query, status
from starlette.concurrency import run_in_threadpool

from app.api.component_dependencies import PROJECT_ROOT
from app.providers.common import ProviderError
from app.providers.component.online import ManufacturerDocumentFinder

router = APIRouter(prefix="/api/v1/components", tags=["components"])


@router.get("/sources")
async def search_component_sources(
    model: str = Query(min_length=2, max_length=100),
) -> dict[str, object]:
    """Return official-domain document leads; specifications require verification."""
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    key = os.getenv("PV_COMPONENT_SEARCH_API_KEY", "").strip()
    if not key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Component source search is not configured",
        )
    try:
        finder = ManufacturerDocumentFinder(api_key=key)
        documents = await run_in_threadpool(finder.search, model)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except ProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Component source search failed",
        ) from exc
    return {
        "model": model,
        "documents": [asdict(document) for document in documents],
        "verified": False,
        "note": "核对铭牌完整型号、规格书版本和参数单位后再登记组件目录。",
    }
