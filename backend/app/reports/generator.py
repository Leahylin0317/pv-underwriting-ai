from app.contracts import UnderwritingCase
from app.contracts.enums import (
    DecisionType,
    DetectionStatus,
    InstallationType,
    MaterialCategory,
    MaterialReviewAction,
    ProcessingStatus,
    ProcessingStep,
    ProjectType,
    RiskSeverity,
)

DECISION_LABELS = {
    DecisionType.ACCEPT: "建议承保",
    DecisionType.RECOMMEND_REJECT: "建议拒保",
    DecisionType.SURCHARGE: "建议加费",
    DecisionType.CONDITIONAL_ACCEPT: "建议附条件承保",
    DecisionType.REQUEST_MORE: "建议补充材料",
    DecisionType.MANUAL_REVIEW: "转人工复核",
}

PROJECT_TYPE_LABELS = {
    ProjectType.ROOFTOP: "工商业屋顶式",
    ProjectType.CARPORT: "车棚顶式",
    ProjectType.UNSUPPORTED: "暂不支持",
    ProjectType.UNKNOWN: "未知",
}

INSTALLATION_TYPE_LABELS = {
    InstallationType.COLOR_STEEL_ROOF: "彩钢瓦屋顶",
    InstallationType.FLAT_ROOF: "平屋顶",
    InstallationType.TILE_ROOF: "瓦屋顶",
    InstallationType.CARPORT_ROOF: "车棚屋顶",
    InstallationType.UNKNOWN: "未知",
}

MATERIAL_CATEGORY_LABELS = {
    MaterialCategory.PANORAMA: "项目全景",
    MaterialCategory.ROOF_CONNECTION: "屋顶连接",
    MaterialCategory.PARAPET: "女儿墙或护栏",
    MaterialCategory.WORKSHOP: "厂房内部",
    MaterialCategory.FILING_CERTIFICATE: "备案证明",
    MaterialCategory.GRID_CONNECTION_DOCUMENT: "并网材料",
    MaterialCategory.ELECTRICAL_GROUNDING: "电气接地",
    MaterialCategory.COMPONENT_NAMEPLATE: "组件铭牌",
    MaterialCategory.INVERTER_NAMEPLATE: "逆变器铭牌",
    MaterialCategory.COMBINER_BOX: "汇流箱",
    MaterialCategory.MONITORING_OPTIONAL: "监控材料",
    MaterialCategory.OTHER: "其他材料",
}

MATERIAL_ACTION_LABELS = {
    MaterialReviewAction.PASS: "通过",
    MaterialReviewAction.WARNING: "风险提示",
    MaterialReviewAction.SURCHARGE: "建议加费",
    MaterialReviewAction.RECOMMEND_REJECT: "建议拒保",
    MaterialReviewAction.CONDITIONAL: "建议附加条件",
    MaterialReviewAction.REQUEST_MORE: "补充材料",
    MaterialReviewAction.NOT_APPLICABLE: "不适用",
}

DETECTION_STATUS_LABELS = {
    DetectionStatus.DETECTED: "已识别",
    DetectionStatus.NOT_DETECTED: "未识别到",
    DetectionStatus.UNCERTAIN: "不确定",
    DetectionStatus.NOT_APPLICABLE: "不适用",
}

RISK_SEVERITY_LABELS = {
    RiskSeverity.INFO: "信息",
    RiskSeverity.LOW: "低",
    RiskSeverity.MEDIUM: "中",
    RiskSeverity.HIGH: "高",
    RiskSeverity.CRITICAL: "严重",
    RiskSeverity.UNKNOWN: "未知",
}

PROCESSING_STEP_LABELS = {
    ProcessingStep.MATERIAL_PARSE: "材料解析",
    ProcessingStep.OCR: "文字识别",
    ProcessingStep.VISION: "图片风险识别",
    ProcessingStep.COMPONENT_LOOKUP: "组件参数查询",
    ProcessingStep.WEATHER_LOOKUP: "气象数据查询",
    ProcessingStep.RULE_ENGINE: "规则判断",
    ProcessingStep.DECISION: "综合决策",
}

PROCESSING_STATUS_LABELS = {
    ProcessingStatus.SUCCESS: "成功",
    ProcessingStatus.PARTIAL: "部分成功",
    ProcessingStatus.FAILED: "失败",
}


def _display(value: object | None) -> str:
    if value is None or value == "":
        return "未提供"
    return str(value)


def _table_cell(value: object | None) -> str:
    return _display(value).replace("|", "\\|").replace("\n", " ")


def _bullet_section(title: str, values: list[str]) -> list[str]:
    lines = [f"### {title}", ""]

    if values:
        lines.extend(f"- {value}" for value in values)
    else:
        lines.append("- 无")

    lines.append("")
    return lines


def generate_markdown_report(case: UnderwritingCase) -> str:
    """把结构化核保案件转换为便于业务人员阅读的 Markdown 报告。"""

    project = case.project

    lines = [
        "# 分布式光伏财产险 AI 核保报告",
        "",
        "> 本报告由系统根据当前材料自动生成，最终承保结论需由授权核保人员确认。",
        "",
        "## 1. 案件概况",
        "",
        "| 项目 | 内容 |",
        "| --- | --- |",
        f"| 案件编号 | {_table_cell(case.case_id)} |",
        f"| 项目名称 | {_table_cell(project.project_name)} |",
        f"| 被保险人 | {_table_cell(project.insured_name)} |",
        f"| 项目单位 | {_table_cell(project.project_entity)} |",
        f"| 项目类型 | {PROJECT_TYPE_LABELS[project.project_type]} |",
        f"| 安装类型 | {INSTALLATION_TYPE_LABELS[project.installation_type]} |",
        f"| 项目地址 | {_table_cell(project.site_address)} |",
        f"| 组件型号 | {_table_cell(project.component_model)} |",
        f"| 计划起保日期 | {_table_cell(project.proposed_start_date)} |",
        "",
        "## 2. 综合核保意见",
        "",
    ]

    if case.decision is None:
        lines.extend(
            [
                "- 建议结论：尚未生成",
                "- 当前状态：等待规则判断或人工复核",
                "",
            ]
        )
    else:
        decision = case.decision

        lines.extend(
            [
                f"- 建议结论：**{DECISION_LABELS[decision.decision]}**",
                f"- 结论生成时间：{decision.generated_at.isoformat()}",
                "",
            ]
        )

        lines.extend(_bullet_section("判断理由", decision.reasons))
        lines.extend(
            _bullet_section(
                "需要补充的材料",
                decision.missing_requirements,
            )
        )
        lines.extend(
            _bullet_section(
                "附加承保条件",
                decision.conditions,
            )
        )
        lines.extend(_bullet_section("风险提示", decision.warnings))

    material_by_id = {
        material.material_id: material
        for material in case.materials
    }

    lines.extend(
        [
            "## 3. 材料审核结果",
            "",
            "| 文件 | 材料类别 | 审核动作 | 人工复核 | 原因 |",
            "| --- | --- | --- | --- | --- |",
        ]
    )

    if case.material_reviews:
        for review in case.material_reviews:
            material = material_by_id[review.material_id]
            reasons = "；".join(review.reasons) or "无"
            manual_review = (
                "是" if review.requires_manual_review else "否"
            )

            lines.append(
                f"| {_table_cell(material.file_name)} "
                f"| {MATERIAL_CATEGORY_LABELS[material.category]} "
                f"| {MATERIAL_ACTION_LABELS[review.action]} "
                f"| {manual_review} "
                f"| {_table_cell(reasons)} |"
            )
    else:
        lines.append("| 无 | 无 | 无 | 无 | 无 |")

    lines.extend(
        [
            "",
            "## 4. 图片风险识别结果",
            "",
            "| 材料 | 风险点 | 状态 | 严重程度 | 置信度 | 判断依据 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )

    if case.findings:
        for finding in case.findings:
            material = material_by_id[finding.material_id]

            lines.append(
                f"| {_table_cell(material.file_name)} "
                f"| {_table_cell(finding.label)} "
                f"| {DETECTION_STATUS_LABELS[finding.detection_status]} "
                f"| {RISK_SEVERITY_LABELS[finding.severity]} "
                f"| {finding.confidence:.2f} "
                f"| {_table_cell(finding.evidence_text)} |"
            )
    else:
        lines.append("| 无 | 无 | 无 | 无 | 无 | 无 |")

    lines.extend(
        [
            "",
            "## 5. 处理留痕",
            "",
            "| 步骤 | 执行方 | 模型 | 状态 | 耗时（毫秒） |",
            "| --- | --- | --- | --- | --- |",
        ]
    )

    if case.processing_trace:
        for trace in case.processing_trace:
            lines.append(
                f"| {PROCESSING_STEP_LABELS[trace.step]} "
                f"| {_table_cell(trace.provider)} "
                f"| {_table_cell(trace.model)} "
                f"| {PROCESSING_STATUS_LABELS[trace.status]} "
                f"| {trace.latency_ms} |"
            )
    else:
        lines.append("| 无 | 无 | 无 | 无 | 无 |")

    return "\n".join(lines).rstrip() + "\n"
