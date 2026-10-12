"""Wind evidence gate and auditable R/F calculation."""

from __future__ import annotations

from app.contracts.catastrophe_evidence import (
    WindAnnualResult,
    WindComparisonResult,
    WindEngineeringEvidence,
)
from app.contracts.profiles import ComponentProfile
from app.contracts.enums import ParameterApplicabilityStatus


def _same_model(left: str, right: str) -> bool:
    return left.strip().casefold() == right.strip().casefold()


def assess_wind_evidence(
    evidence: WindEngineeringEvidence,
    *,
    component: ComponentProfile | None,
    project_model: str | None = None,
) -> tuple[ParameterApplicabilityStatus, WindComparisonResult]:
    """Only compare attested pressure series and the matching installed module.

    ``maximum_pa`` must already be an engineering pressure with the same
    definition as ``capacity_pa``. Historical 10 m gust speed is never converted
    into a project design pressure here.
    """
    missing: list[str] = []
    incompatible: list[str] = []

    if project_model and not _same_model(evidence.component_model, project_model):
        incompatible.append("工程证据的完整型号与投保项目型号不一致")
    if component and not _same_model(evidence.component_model, component.component_model):
        incompatible.append("工程证据的完整型号与组件查询结果不一致")
    if component and component.manufacturer and not _same_model(
        evidence.manufacturer, component.manufacturer
    ):
        incompatible.append("工程证据的厂商与组件查询结果不一致")
    if component and component.wind_load_pa is not None and abs(
        evidence.capacity_pa - component.wind_load_pa
    ) > max(1.0, component.wind_load_pa * 0.001):
        incompatible.append("厂家文件抗风值与组件目录值冲突，需核对版本和安装条件")

    if evidence.mounting_match is False:
        incompatible.append("现场固定方式与厂家手册适用条件不匹配")
    elif evidence.mounting_match is None:
        missing.append("厂家要求与现场固定方式的人工核验结论")
    if not evidence.mounting_material_ids:
        missing.append("可定位的现场安装材料编号")
    if not evidence.installation_reviewer or not evidence.installation_reviewed_at:
        missing.append("安装条件核验人和时间")

    installation_status = (
        ParameterApplicabilityStatus.NOT_APPLICABLE
        if incompatible
        else ParameterApplicabilityStatus.PENDING_CONFIRMATION
        if missing
        else ParameterApplicabilityStatus.USABLE
    )

    if not evidence.project_location_confirmed or not evidence.location_evidence:
        missing.append("经交叉核验的项目位置及证据来源")
    if not evidence.comparison_basis or not evidence.comparison_method_reference:
        missing.append("同单位同定义的比较依据和批准方法")
    elif evidence.comparison_basis.strip().casefold() != evidence.capacity_definition.strip().casefold():
        incompatible.append("项目侧压力定义与厂家抗风能力定义不一致")
    if not evidence.comparison_reviewer or not evidence.comparison_reviewed_at:
        missing.append("比较方法核验人和时间")

    annual_results: list[WindAnnualResult] = []
    valid_values: list[float] = []
    for item in sorted(evidence.annual_pressures, key=lambda row: row.year):
        included = item.valid_days == item.expected_days and item.maximum_pa is not None
        reason = "全年有效，参与复算" if included else "年度缺测或无极值，已排除且未填零"
        annual_results.append(WindAnnualResult(
            year=item.year,
            maximum_pa=item.maximum_pa,
            valid_days=item.valid_days,
            expected_days=item.expected_days,
            included=included,
            reason=reason,
            source_url=item.source_url,
            dataset=item.dataset,
            grid_reference=item.grid_reference,
        ))
        if included:
            valid_values.append(item.maximum_pa)

    if not valid_values:
        missing.append("至少一个完整且非缺测的可比年度压力极值")
    status = "incompatible" if incompatible else "incomplete" if missing else "calculated"
    explanation = (
        "；".join(dict.fromkeys([*incompatible, *missing]))
        if status != "calculated"
        else "仅完成已核验输入的历史压力与组件参数比较；不代表真实出险概率或整站结构合格"
    )
    if status != "calculated":
        return installation_status, WindComparisonResult(
            status=status,
            capacity_pa=evidence.capacity_pa,
            valid_year_count=len(valid_values),
            excluded_year_count=len(annual_results) - len(valid_values),
            annual_results=annual_results,
            missing_requirements=list(dict.fromkeys([*incompatible, *missing])),
            method_reference=evidence.comparison_method_reference,
            explanation=explanation,
        )

    historical_maximum = max(valid_values)
    r = historical_maximum / evidence.capacity_pa
    f = 100.0 * sum(value > evidence.capacity_pa for value in valid_values) / len(valid_values)
    return installation_status, WindComparisonResult(
        status="calculated",
        capacity_pa=evidence.capacity_pa,
        historical_maximum_pa=historical_maximum,
        r_historical_over_capacity=r,
        f_exceedance_percent=f,
        valid_year_count=len(valid_values),
        excluded_year_count=len(annual_results) - len(valid_values),
        annual_results=annual_results,
        technical_result=(
            "historical_exceedance" if f > 0 else "within_historical_sample"
        ),
        method_reference=evidence.comparison_method_reference,
        explanation=explanation,
    )
