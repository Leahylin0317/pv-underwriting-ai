from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.api import ocr_router, router

app = FastAPI(
    title="分布式光伏财产险 AI 智能核保",
    description="分布式光伏投保材料解析、风险识别和核保决策接口。",
    version="0.1.0",
)

app.include_router(router)
app.include_router(ocr_router)


def custom_openapi() -> dict[str, Any]:
    """Add the binary hint required by Swagger UI for multiple file inputs."""

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

    request_schema = openapi_schema[
        "paths"
    ][
        "/api/v1/files/inspect"
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

    component_name = request_schema[
        "$ref"
    ].rsplit(
        "/",
        maxsplit=1,
    )[-1]

    file_items = openapi_schema[
        "components"
    ][
        "schemas"
    ][
        component_name
    ][
        "properties"
    ][
        "files"
    ][
        "items"
    ]

    file_items["format"] = "binary"

    app.openapi_schema = openapi_schema
    return openapi_schema


app.openapi = custom_openapi
