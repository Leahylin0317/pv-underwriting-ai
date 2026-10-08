"""Search and human correction endpoints for photovoltaic module parameters."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote_plus, urlparse

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query, status
from starlette.concurrency import run_in_threadpool

from app.api.component_dependencies import (
    PROJECT_ROOT,
    get_component_catalog_path,
)
from app.api.schemas import ComponentCorrectionSubmission
from app.contracts import ComponentProfile
from app.providers import ProviderError
from app.providers.component import (
    CatalogComponentProvider,
    ComponentResearchAgent,
    normalize_component_model,
)
from app.providers.component.research import (
    ComponentDocumentLead,
    ComponentSearchStage,
    stage_as_dict,
)

router = APIRouter(prefix="/api/v1/components", tags=["components"])


def _correction_path() -> Path:
    configured = os.getenv(
        "PV_COMPONENT_CORRECTIONS_PATH",
        "outputs/component-corrections.json",
    ).strip() or "outputs/component-corrections.json"
    path = Path(configured).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def _read_profiles(path: Path) -> list[ComponentProfile]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(raw, list):
            raise TypeError("correction file root must be a list")
        return [ComponentProfile.model_validate(item) for item in raw]
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Component correction catalog is invalid",
        ) from exc


def _search_agent() -> ComponentResearchAgent:
    domains = tuple(
        part.strip()
        for part in os.getenv("PV_COMPONENT_TRUSTED_SOURCE_DOMAINS", "").split(",")
        if part.strip()
    )
    return ComponentResearchAgent(
        api_key=os.getenv("PV_COMPONENT_SEARCH_API_KEY", "").strip(),
        trusted_domains=domains,
    )


def _local_variant_candidate_stage(
    model: str,
    candidates: list[ComponentProfile],
) -> ComponentSearchStage | None:
    documents: list[ComponentDocumentLead] = []
    for candidate in candidates:
        source_url = candidate.source_url
        parsed = urlparse(source_url or "")
        if parsed.scheme != "https" or not parsed.hostname:
            continue
        available = []
        for field, label, unit in (
            ("rated_power_w", "额定功率", "W"),
            ("hail_resistance_mm", "冰雹试验直径", "mm"),
            ("hail_impact_velocity_m_s", "冰雹试验速度", "m/s"),
            ("front_static_load_pa", "正面最大静载", "Pa"),
            ("back_static_load_pa", "背面最大静载", "Pa"),
        ):
            value = getattr(candidate, field)
            if value is not None:
                available.append(f"{label} {value:g} {unit}")
        parameter_summary = "；".join(available) or "该目录记录没有可展示的参数"
        documents.append(
            ComponentDocumentLead(
                title=candidate.component_model,
                url=source_url,
                description=(
                    f"本地目录候选，参数：{parameter_summary}。"
                    "候选型号与输入型号的后缀/版本尚未确认；请先核对铭牌，确认后再以完整型号查询。"
                ),
                stage="local_catalog_variant_candidates",
                source_domain=parsed.hostname.lower(),
                model_match="variant_candidate_requires_nameplate_confirmation",
            )
        )
    if not documents:
        return None
    return ComponentSearchStage(
        stage="local_catalog_variant_candidates",
        label="本地目录可能型号（需核对铭牌后缀）",
        query=model,
        status="candidate_review_required",
        documents=documents,
        note=(
            "这些候选仅用于定位资料，不会自动用于核保。请核对组件铭牌上的完整型号和版本；"
            "确认后将完整型号重新查询，再按来源逐字段审核参数。"
        ),
    )
@router.get("/sources")
async def search_component_sources(
    model: str = Query(min_length=2, max_length=100),
    manufacturer: str = Query(default="", max_length=120),
    series: str = Query(default="", max_length=100),
) -> dict[str, object]:
    """Run ordered search stages and return document leads, never parsed ratings."""
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    manufacturer = manufacturer.strip()
    local_catalog: CatalogComponentProvider | None = None
    variant_candidates: list[ComponentProfile] = []
    try:
        local_catalog = CatalogComponentProvider.from_json_file(get_component_catalog_path())
        if not manufacturer:
            profile = local_catalog.lookup(model)
            if profile is not None:
                manufacturer = profile.manufacturer or ""
        variant_candidates = local_catalog.find_variant_candidates(model)
    except ProviderError:
        # Search can still use the remote search service and Solar-Stack's
        # browser entry if the local component catalogue is not readable.
        local_catalog = None

    try:
        stages = await run_in_threadpool(
            _search_agent().search,
            model=model,
            manufacturer=manufacturer,
            series=series,
        )
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

    candidate_stage = _local_variant_candidate_stage(model, variant_candidates)
    if candidate_stage is not None:
        stages.insert(1, candidate_stage)

    has_search_api = bool(os.getenv("PV_COMPONENT_SEARCH_API_KEY", "").strip())
    web_query = f'"{model}" {manufacturer} photovoltaic module datasheet'.strip()
    return {
        "model": model,
        "manufacturer": manufacturer or None,
        "series": series or None,
        "stages": [stage_as_dict(stage) for stage in stages],
        "solar_stack_search_url": (
            "https://www.solar-stack.com/en/panel?q="
            + quote_plus(model)
        ),
        "browser_search_links": [
            {
                "label": "打开 Google 网页检索",
                "url": "https://www.google.com/search?q=" + quote_plus(web_query),
            },
            {
                "label": "打开 Bing 网页检索",
                "url": "https://www.bing.com/search?q=" + quote_plus(web_query),
            },
        ],
        "search_api_configured": has_search_api,
        "verified": False,
        "next_step": (
            "逐项打开原始 Datasheet，确认完整型号、市场版本、单位、试验方法和适用条件。"
            "完成后可在工作台提交人工补正；补正只填充当前目录缺失值。"
        ),
    }


@router.post("/corrections", status_code=status.HTTP_201_CREATED)
async def save_component_correction(
    submission: ComponentCorrectionSubmission,
) -> dict[str, object]:
    """Persist operator-verified values as a local overlay for later cases."""
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    correction_path = _correction_path()
    try:
        correction_path.parent.mkdir(parents=True, exist_ok=True)
        existing_corrections = _read_profiles(correction_path)
        base = CatalogComponentProvider.from_json_file(get_component_catalog_path())
    except (OSError, ProviderError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Component catalog is unavailable for correction review",
        ) from exc

    normalized_model = normalize_component_model(submission.component_model)
    current_base = base.lookup(submission.component_model)
    current_manual = next(
        (
            profile for profile in existing_corrections
            if normalize_component_model(profile.component_model) == normalized_model
        ),
        None,
    )
    fields = (
        "rated_power_w",
        "hail_resistance_mm",
        "hail_impact_velocity_m_s",
        "wind_load_pa",
        "snow_load_pa",
        "front_static_load_pa",
        "back_static_load_pa",
    )
    conflicts = [
        field
        for field in fields
        if getattr(submission, field) is not None
        and any(
            getattr(profile, field) is not None
            and getattr(profile, field) != getattr(submission, field)
            for profile in (current_base, current_manual)
            if profile is not None
        )
    ]
    if conflicts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Correction conflicts with an existing non-empty catalogue value: "
                + ", ".join(conflicts)
                + ". Resolve the conflict by reviewing the exact manufacturer document."
            ),
        )

    profile_values = {
        field: getattr(submission, field)
        for field in fields
    }
    candidate = ComponentProfile(
        component_model=submission.component_model,
        manufacturer=submission.manufacturer,
        **profile_values,
        market_version=submission.market_version,
        model_derivation_method="human_verified_exact_model",
        source_document_type=submission.source_document_type,
        source_note=(
            f"人工逐项核对；复核人：{submission.reviewer_name}；"
            f"精确型号已与铭牌/规格书核对。{submission.source_note}"
        ),
        source_url=submission.source_url,
        source_name=f"人工补正 Datasheet：{submission.source_document_type}",
        retrieved_at=datetime.now(UTC),
        match_confidence=0.95,
        parameter_sources=submission.parameter_sources,
        lookup_notes=[
            "此值由操作员手动对照完整型号的原始资料登记；仍需结合地区版本、安装和试验条件复核。",
            "人工补正仅填充原目录缺失字段，不会覆盖现有非空数值。",
        ],
    )

    if current_manual is not None:
        merged_values = {
            field: getattr(current_manual, field)
            if getattr(current_manual, field) is not None
            else getattr(candidate, field)
            for field in fields
        }
        candidate = current_manual.model_copy(
            update={
                **merged_values,
                "parameter_sources": {
                    **current_manual.parameter_sources,
                    **candidate.parameter_sources,
                },
                "source_name": f"{current_manual.source_name}; {candidate.source_name}",
                "source_url": candidate.source_url,
                "source_note": f"{current_manual.source_note}\n{candidate.source_note}",
                "lookup_notes": [*current_manual.lookup_notes, *candidate.lookup_notes],
                "retrieved_at": candidate.retrieved_at,
            }
        )
        existing_corrections = [
            candidate
            if normalize_component_model(profile.component_model) == normalized_model
            else profile
            for profile in existing_corrections
        ]
    else:
        existing_corrections.append(candidate)

    payload = json.dumps(
        [profile.model_dump(mode="json") for profile in existing_corrections],
        ensure_ascii=False,
        indent=2,
    ) + "\n"
    temporary_path = correction_path.with_suffix(correction_path.suffix + ".tmp")
    try:
        temporary_path.write_text(payload, encoding="utf-8")
        temporary_path.replace(correction_path)
    except OSError as exc:
        temporary_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Component correction could not be saved",
        ) from exc

    return {
        "status": "saved_for_future_cases",
        "component_model": submission.component_model,
        "saved_field_names": [
            field for field in fields if getattr(submission, field) is not None
        ],
        "note": (
            "人工补正已写入本机组件目录覆盖文件；当前已保存案件不会被回写，"
            "新案件会使用这些补充值。"
        ),
        "reviewer_name": submission.reviewer_name,
    }
