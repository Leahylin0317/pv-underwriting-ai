from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.api import (
    ocr_router,
    router,
    underwriting_router,
)

app = FastAPI(
    title="分布式光伏财产险 AI 智能核保",
    description="分布式光伏投保材料解析、风险识别和核保决策接口。",
    version="0.1.0",
)

app.include_router(router)
app.include_router(ocr_router)
app.include_router(underwriting_router)


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
