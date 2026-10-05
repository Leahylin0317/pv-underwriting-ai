import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from app.api import (
    auth_router,
    case_router,
    component_router,
    geocoding_router,
    ocr_router,
    report_router,
    router,
    underwriting_router,
)
from app.security import AuthRepository, auth_enabled
from app.security.middleware import RoleAccessMiddleware
from app.storage import AnalysisJobRepository, CaseRepository


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await run_in_threadpool(AnalysisJobRepository().fail_incomplete_jobs)
    retention_days = int(os.getenv("PV_CASE_RETENTION_DAYS", "0"))
    if retention_days < 0:
        raise ValueError("PV_CASE_RETENTION_DAYS must be zero or greater")
    if retention_days:
        await run_in_threadpool(
            CaseRepository().purge_expired_cases,
            retention_days=retention_days,
        )
    if auth_enabled():
        await run_in_threadpool(AuthRepository().ensure_initial_admin)
    yield

app = FastAPI(
    title="分布式光伏财产险 AI 智能核保",
    description="分布式光伏投保材料解析、风险识别和核保决策接口。",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(RoleAccessMiddleware)

app.include_router(router)
app.include_router(auth_router)
app.include_router(ocr_router)
app.include_router(case_router)
app.include_router(component_router)
app.include_router(geocoding_router)
app.include_router(underwriting_router)
app.include_router(report_router)


@app.get("/", include_in_schema=False)
def underwriting_workspace() -> FileResponse:
    """提供本地核保工作台页面。"""
    page = Path(__file__).resolve().parents[2] / "frontend" / "index.html"
    return FileResponse(page, media_type="text/html; charset=utf-8")


def _set_file_array_binary(
    openapi_schema: dict[str, Any],
    path: str,
) -> None:
    request_schema = openapi_schema[
        "paths"
    ][
        path
    ][
        "post"
    ][
        "requestBody"
    ][
        "content"
    ][
        "multipart/form-data"
    ][
        "schema"
    ]

    if "$ref" in request_schema:
        component_name = request_schema[
            "$ref"
        ].rsplit(
            "/",
            maxsplit=1,
        )[-1]

        properties = openapi_schema[
            "components"
        ][
            "schemas"
        ][
            component_name
        ][
            "properties"
        ]
    else:
        properties = request_schema[
            "properties"
        ]

    properties[
        "files"
    ][
        "items"
    ][
        "format"
    ] = "binary"


def custom_openapi() -> dict[str, Any]:
    """Add binary hints required by Swagger UI for file arrays."""

    if app.openapi_schema is not None:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        summary=app.summary,
        description=app.description,
        routes=app.routes,
    )

    _set_file_array_binary(
        openapi_schema,
        "/api/v1/files/inspect",
    )
    _set_file_array_binary(
        openapi_schema,
        "/api/v1/underwriting/analyze",
    )

    app.openapi_schema = openapi_schema
    return openapi_schema


app.openapi = custom_openapi
