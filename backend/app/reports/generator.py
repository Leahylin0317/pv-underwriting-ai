from app.contracts import RuleExplanation, UnderwritingCase
from app.contracts.enums import (
    DecisionType,
    DetectionStatus,
    InstallationType,
    MaterialCategory,
    MaterialReviewAction,
    OcrValueStatus,
    ProcessingStatus,
    ProcessingStep,
    ProjectType,
    RiskSeverity,
)
from app.rules.explanations import explain_rule

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
    MaterialCategory.COMPONENT_SURFACE: "组件表面照片",
    MaterialCategory.INVERTER_NAMEPLATE: "逆变器铭牌",
    MaterialCategory.COMBINER_BOX: "汇流箱",
    MaterialCategory.MONITORING_OPTIONAL: "监控材料",
    MaterialCategory.EQUIPMENT_INVENTORY: "设备清单",
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

OCR_FIELD_LABELS = {
    "project_name": "项目名称",
    "project_entity": "项目单位",
    "insured_name": "被保险人",
    "insured_address": "被保险地址",
    "site_address": "项目地址",
    "component_model": "组件型号",
    "inverter_model": "逆变器型号",
    "rated_power_w": "额定功率（W）",
    "serial_number": "序列号",
    "grid_connection_date": "并网日期",
    "grounding_resistance_ohm": "接地电阻（Ω）",
    "inspection_date": "检测日期",
    "inspection_result": "检测结论",
    "monitoring_present": "监控系统状态",
}

OCR_STATUS_LABELS = {
    OcrValueStatus.EXTRACTED: "已提取",
    OcrValueStatus.MISSING: "缺失",
    OcrValueStatus.UNCERTAIN: "不确定",
}

DETECTION_STATUS_LABELS = {
    DetectionStatus.DETECTED: "已识别",
    DetectionStatus.NOT_DETECTED: "未识别到",
    DetectionStatus.UNCERTAIN: "不确定",
    DetectionStatus.NOT_APPLICABLE: "不适用",
}

ENVIRONMENT_RELATION_LABELS = {
    "project_site": "项目现场本身",
    "operational_surroundings": "项目邻近周边（边界待核）",
    "distant_background": "远处背景景物",
    "uncertain": "现场关系不确定",
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
    ProcessingStep.EQUIPMENT_INVENTORY: "设备清单解析",
    ProcessingStep.VISION: "图片风险识别",
    ProcessingStep.COMPONENT_LOOKUP: "组件参数查询",
    ProcessingStep.WEATHER_LOOKUP: "气象数据查询",
    ProcessingStep.CATASTROPHE_ASSESSMENT: "灾害风险评估",
    ProcessingStep.MAP_REVIEW: "地图辅助复核",
    ProcessingStep.RULE_ENGINE: "规则判断",
    ProcessingStep.DECISION: "综合决策",
}

PROCESSING_STATUS_LABELS = {
    ProcessingStatus.SUCCESS: "成功",
    ProcessingStatus.PARTIAL: "部分成功",
    ProcessingStatus.FAILED: "失败",
}

PROCESSING_STEP_PURPOSE = {
    ProcessingStep.MATERIAL_PARSE: "检查文件可读性并提取材料基础信息",
    ProcessingStep.OCR: "从文档或图片提取可核对的文字字段",
    ProcessingStep.EQUIPMENT_INVENTORY: "解析设备清单并识别设备型号和数量",
    ProcessingStep.VISION: "识别图像中的风险观察，不单独决定整单结论",
    ProcessingStep.COMPONENT_LOOKUP: "查询组件型号和抗灾参数来源",
    ProcessingStep.WEATHER_LOOKUP: "查询项目坐标对应的历史气象指标",
    ProcessingStep.CATASTROPHE_ASSESSMENT: "比较组件额定能力与历史灾害指标",
    ProcessingStep.MAP_REVIEW: "记录人工查看第三方地图页面后的补充观察，不改变自动结论",
    ProcessingStep.RULE_ENGINE: "把材料事实与确定性规则逐项比对",
    ProcessingStep.DECISION: "按固定优先顺序汇总材料动作和评估结果",
}

RESISTANCE_LABELS = {
    "low": "低",
    "medium": "中",
    "high": "高",
    "unknown": "未知",
}

LOSS_RISK_LABELS = {
    "low": "低",
    "medium": "中",
    "high": "高",
    "critical": "严重",
    "unknown": "未评估",
}


def _display(value: object | None) -> str:
    if value is None or value == "":
        return "未提供"
    return str(value)


def _display_measurement(value: float | None) -> str:
    if value is None:
        return "未提供"
    return f"{value:g}"


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


def _rule_explanation_lines(
    rule_ids: list[str], explanation_by_id: dict[str, RuleExplanation]
) -> list[str]:
    if not rule_ids:
        return ["- 命中规则：无"]

    lines = []
    for rule_id in rule_ids:
        explanation = explanation_by_id.get(rule_id) or explain_rule(rule_id)
        lines.append(
            f"- **{rule_id}｜{explanation.title}**："
            f"触发条件：{_table_cell(explanation.trigger)}；"
            f"处理作用：{_table_cell(explanation.effect)}"
        )
    return lines


def _decision_priority_explanation(decision: DecisionType) -> str:
    return {
        DecisionType.RECOMMEND_REJECT: "命中建议拒保条件，因此输出建议拒保。",
        DecisionType.REQUEST_MORE: "未先命中建议拒保条件，但存在必需信息或材料缺口，因此输出补充材料。",
        DecisionType.MANUAL_REVIEW: "存在位置冲突或其他需人工核实事项，因此转人工复核；位置冲突可优先于一般补材要求。",
        DecisionType.SURCHARGE: "前序拒保、补充材料和人工复核条件均未触发，规则命中加费建议。",
        DecisionType.CONDITIONAL_ACCEPT: "前序更高优先级条件均未触发，规则命中附条件承保建议。",
        DecisionType.ACCEPT: "前序风险、资料缺口和人工复核条件均未触发，规则输出建议承保。",
    }[decision]


def generate_markdown_report(
    case: UnderwritingCase,
    *,
    human_reviews: list[dict[str, str]] | None = None,
) -> str:
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
        f"| 企业所属行业 | {_table_cell(project.industry_name)} |",
        f"| 项目类型 | {PROJECT_TYPE_LABELS[project.project_type]} |",
        f"| 安装类型 | {INSTALLATION_TYPE_LABELS[project.installation_type]} |",
        f"| 项目地址 | {_table_cell(project.site_address)} |",
        f"| 组件型号 | {_table_cell(project.component_model)} |",
        f"| 计划起保日期 | {_table_cell(project.proposed_start_date)} |",
        f"| 被保险地址 | {_table_cell(project.insured_address)} |",
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

    if case.package_assessment is not None:
        package = case.package_assessment
        lines.extend(
            [
                "### 材料包完整性",
                "",
                f"- 图片材料：{package.image_count} 张；全景照：{package.panorama_count} 张",
                (
                    f"- 备案证：{'已提供' if package.has_filing_certificate else '缺失'}；"
                    f"正面平视：{'已标注' if package.has_front_level_panorama else '未确认'}；"
                    f"俯拍：{'已标注' if package.has_overhead_panorama else '未确认'}"
                ),
                "- 待补充：" + ("；".join(package.missing_requirements) or "无"),
                "",
            ]
        )

    if case.location_assessment is not None:
        location = case.location_assessment
        status_labels = {
            "verified": "多来源位置一致",
            "single_source": "仅一个位置来源，待核实",
            "conflict": "位置冲突，暂停自动通过",
            "uncertain": "位置证据不足，待核实",
            "missing": "缺少位置证据",
        }
        lines.extend([
            "### 项目位置核验",
            "",
            f"- 核验结果：{status_labels[location.status]}",
            "- 气象查询位置：" + (
                f"{location.weather_coordinate_source}（{'已交叉核验' if location.weather_coordinates_verified else '未经交叉核验，仅作候选参考'}）"
                if location.weather_coordinate_source else "未取得可用坐标"
            ),
            *[f"- 说明：{note}" for note in location.notes],
            "",
            "| 来源 | 文件 | 地址 | 经度 | 纬度 | 坐标系 | 地图定位精度 |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ])
        for evidence in location.evidence:
            lines.append(
                f"| {_table_cell(evidence.source)} | {_table_cell(evidence.file_name or evidence.material_id)} | "
                f"{_table_cell(evidence.address)} | {_table_cell(evidence.longitude)} | "
                f"{_table_cell(evidence.latitude)} | {_table_cell(evidence.coordinate_system)} | "
                f"{_table_cell(evidence.geocode_level)} |"
            )
        lines.append("")

    material_by_id = {
        material.material_id: material
        for material in case.materials
    }
    explanation_by_id = {
        item.rule_id: item
        for item in (case.decision.rule_explanations if case.decision else [])
    }
    lines.extend(
        [
            "## 判断过程与追溯",
            "",
            "- **模型与规则分工：** OCR/视觉模型提供字段提取、风险观察和证据文字；模型置信度是参考分数，尚未经过概率校准。材料动作和整单建议由程序规则汇总，模型不直接生成整单结论。",
            "- **整单汇总顺序：** 明确拒保事实 → 位置冲突人工复核 → 补充材料 → 其他人工复核 → 建议加费 → 附条件承保 → 建议承保；按顺序选择首个成立的结果。",
            "",
        ]
    )
    if case.decision is None:
        lines.extend(["- 当前尚未生成整单结论。", ""])
    else:
        decision = case.decision
        lines.extend(
            [
                f"- **本案结论：** {DECISION_LABELS[decision.decision]}。{_decision_priority_explanation(decision.decision)}",
                "- **参与整单汇总的规则：**",
                *[
                    f"  {line}"
                    for line in _rule_explanation_lines(
                        decision.decisive_rule_ids,
                        explanation_by_id,
                    )
                ],
                "",
            ]
        )

    findings_by_id = {item.finding_id: item for item in case.findings}
    ocr_fields_by_id = {item.field_id: item for item in case.ocr_fields}
    lines.extend(["### 单份材料的证据链", ""])
    if case.material_reviews:
        for review in case.material_reviews:
            material = material_by_id.get(review.material_id)
            material_name = material.file_name if material is not None else review.material_id
            lines.extend(
                [
                    f"#### {_table_cell(material_name)} → {MATERIAL_ACTION_LABELS[review.action]}",
                    "",
                    "- 规则理由：" + ("；".join(review.reasons) or "未提供文字理由"),
                    "- 命中规则：",
                    *[
                        f"  {line}"
                        for line in _rule_explanation_lines(
                            review.triggered_rule_ids,
                            explanation_by_id,
                        )
                    ],
                    "- 关联视觉证据：",
                ]
            )
            if review.finding_ids:
                for finding_id in review.finding_ids:
                    finding = findings_by_id.get(finding_id)
                    if finding is None:
                        lines.append(f"  - {finding_id}：引用记录未找到。")
                        continue
                    environment_relation = (
                        ENVIRONMENT_RELATION_LABELS.get(
                            finding.environment_relation.value,
                            finding.environment_relation.value,
                        )
                        if finding.category.value.endswith("_environment")
                        else "不适用"
                    )
                    lines.append(
                        f"  - {finding_id}｜{_table_cell(finding.label)}｜"
                        f"{DETECTION_STATUS_LABELS[finding.detection_status]}｜"
                        f"环境关系：{environment_relation}｜"
                        f"证据：{_table_cell(finding.evidence_text)}｜"
                        f"参考置信度：{finding.confidence:.2f}（未校准）"
                    )
            else:
                lines.append("  - 无直接关联的视觉发现。")
            lines.append("- 关联 OCR 字段：")
            if review.ocr_field_ids:
                for field_id in review.ocr_field_ids:
                    field = ocr_fields_by_id.get(field_id)
                    if field is None:
                        lines.append(f"  - {field_id}：引用记录未找到。")
                        continue
                    field_label = OCR_FIELD_LABELS.get(field.field_name, field.field_name)
                    lines.append(
                        f"  - {field_id}｜{field_label}｜原文：{_table_cell(field.raw_value)}｜"
                        f"规范值：{_table_cell(field.normalized_value)}｜"
                        f"状态：{OCR_STATUS_LABELS[field.value_status]}｜"
                        f"参考置信度：{field.confidence:.2f}（未校准）"
                    )
            else:
                lines.append("  - 无直接关联的 OCR 字段。")
            lines.append("")
    else:
        lines.extend(["- 当前没有生成逐份材料审核记录。", ""])

    if case.catastrophe_assessment is not None:
        lines.extend(
            [
                "### 自然灾害评估引用的规则",
                "",
                *[
                    f"  {line}"
                    for line in _rule_explanation_lines(
                        case.catastrophe_assessment.triggered_rule_ids,
                        explanation_by_id,
                    )
                ],
                "",
            ]
        )

    lines.extend(["### 自动处理步骤及其用途", ""])
    if case.processing_trace:
        for trace in case.processing_trace:
            step_name = PROCESSING_STEP_LABELS[trace.step]
            purpose = PROCESSING_STEP_PURPOSE[trace.step]
            detail = (
                f"{step_name}：{purpose}；执行方 {_table_cell(trace.provider)}"
                f"；模型 {_table_cell(trace.model)}；状态 {PROCESSING_STATUS_LABELS[trace.status]}"
                f"；耗时 {trace.latency_ms} ms。"
            )
            if trace.error_code or trace.error_message:
                detail += f" 留痕错误：{_table_cell(trace.error_code)} {_table_cell(trace.error_message)}。"
            if trace.status in {ProcessingStatus.PARTIAL, ProcessingStatus.FAILED}:
                detail += " 该步骤未完整执行，因此整单会提示人工复核。"
            lines.append(f"- {detail}")
    else:
        lines.append("- 当前没有自动处理留痕。")
    lines.append("")

    reviewed_finding_ids = {
        finding_id
        for review in case.material_reviews
        for finding_id in review.finding_ids
    }
    report_findings = (
        [item for item in case.findings if item.finding_id in reviewed_finding_ids]
        if case.material_reviews
        else case.findings
    )

    lines.extend(
        [
            "## 3. 材料审核结果",
            "",
            "| 文件 | 材料类别 | 审核动作 | 命中规则 | 人工复核 | 原因 |",
            "| --- | --- | --- | --- | --- | --- |",
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
                f"| {_table_cell('、'.join(review.triggered_rule_ids) or '无')} "
                f"| {manual_review} "
                f"| {_table_cell(reasons)} |"
            )
    else:
        lines.append("| 无 | 无 | 无 | 无 | 无 | 无 |")

    lines.extend(
        [
            "",
            "## 4. OCR 字段提取结果",
            "",
            "| 材料 | 字段 | 状态 | 原文 | 标准化结果 | 识别参考分数（未校准） | 位置 |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )

    if case.ocr_fields:
        for field in case.ocr_fields:
            material = material_by_id[field.material_id]
            location = (
                "未定位"
                if field.bbox is None
                else (
                    f"({field.bbox.x_min:.2f}, {field.bbox.y_min:.2f})-"
                    f"({field.bbox.x_max:.2f}, {field.bbox.y_max:.2f})"
                )
            )
            lines.append(
                f"| {_table_cell(material.file_name)} "
                f"| {_table_cell(OCR_FIELD_LABELS.get(field.field_name, field.field_name))} "
                f"| {OCR_STATUS_LABELS[field.value_status]} "
                f"| {_table_cell(field.raw_value)} "
                f"| {_table_cell(field.normalized_value)} "
                f"| {field.confidence:.2f} "
                f"| {location} |"
            )
    else:
        lines.append("| 无 | 无 | 无 | 无 | 无 | 无 | 无 |")

    if case.equipment_inventory:
        lines.extend(
            [
                "",
                "## 设备清单结构化结果",
                "",
                "| 来源 | 工作表/行 | 类别 | 名称 | 品牌 | 型号/规格 | 数量 | 单价 | 合计 |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for item in case.equipment_inventory:
            source = material_by_id[item.source_material_id]
            specification = item.specification or ""
            if item.normalized_component_model:
                specification += f"（识别型号：{item.normalized_component_model}"
                if item.rated_power_w is not None:
                    specification += f"，{item.rated_power_w:g} W"
                specification += "）"
            lines.append(
                f"| {_table_cell(source.file_name)} "
                f"| {_table_cell(f'{item.worksheet_name}/{item.row_number}')} "
                f"| {_table_cell(item.item_category)} "
                f"| {_table_cell(item.item_name)} "
                f"| {_table_cell(item.manufacturer)} "
                f"| {_table_cell(specification)} "
                f"| {_table_cell(item.quantity)} "
                f"| {_table_cell(item.unit_price)} "
                f"| {_table_cell(item.total_price)} |"
            )
        lines.append("")

    lines.extend(
        [
            "",
            "## 5. 图片风险识别结果",
            "",
            "| 材料 | 风险点 | 状态 | 环境与现场关系 | 严重程度 | 识别参考分数（未校准） | 位置 | 判断依据 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )

    if report_findings:
        for finding in report_findings:
            material = material_by_id[finding.material_id]
            environment_relation = (
                ENVIRONMENT_RELATION_LABELS.get(
                    finding.environment_relation.value,
                    finding.environment_relation.value,
                )
                if finding.category.value.endswith("_environment")
                else "不适用"
            )
            location = (
                "未定位"
                if finding.bbox is None
                else (
                    f"({finding.bbox.x_min:.2f}, {finding.bbox.y_min:.2f})-"
                    f"({finding.bbox.x_max:.2f}, {finding.bbox.y_max:.2f})"
                )
            )

            lines.append(
                f"| {_table_cell(material.file_name)} "
                f"| {_table_cell(finding.label)} "
                f"| {DETECTION_STATUS_LABELS[finding.detection_status]} "
                f"| {environment_relation} "
                f"| {RISK_SEVERITY_LABELS[finding.severity]} "
                f"| {finding.confidence:.2f} "
                f"| {location} "
                f"| {_table_cell(finding.evidence_text)} |"
            )
    else:
        lines.append("| 无 | 无 | 无 | 无 | 无 | 无 | 无 | 无 |")

    lines.extend(["", "## 6. 自然灾害抗灾筛查", ""])
    if case.catastrophe_assessment is None:
        lines.extend(["- 状态：未评估", "- 原因：没有生成组件与气象数据的联合评估", ""])
    else:
        assessment = case.catastrophe_assessment
        ratio_thresholds = (
            (
                f"- 能力比分级门槛：严重不足 < {assessment.critical_shortfall_ratio:.2f}；"
                f"能力不足 < 1.00；余量有限 < {assessment.adequate_margin_ratio:.2f}；"
                "此处为旧版演示算法阈值，未经结构设计或业务审批，不等同工程判断"
            )
            if assessment.critical_shortfall_ratio is not None
            and assessment.adequate_margin_ratio is not None
            else "- 能力比：未计算；现有厂家试验参数与历史天气指标尚无经验证的同口径比较方法"
        )
        lines.extend(
            [
                f"- 抗灾能力等级：{RESISTANCE_LABELS[assessment.resistance_level.value]}",
                f"- 抗灾筛查风险档位：{LOSS_RISK_LABELS[assessment.expected_loss_risk.value]}",
                f"- 评估说明：{_table_cell(assessment.explanation)}",
                "- 逐项因素：" + ("；".join(assessment.factors) or "无"),
                ratio_thresholds,
                "- 规则编号：" + ("、".join(assessment.triggered_rule_ids) or "无"),
                "",
            ]
        )
        if assessment.installation_parameter_reviews:
            hazard_labels = {"wind": "大风", "hail": "冰雹", "snow": "积雪"}
            status_labels = {
                "usable": "可用",
                "not_applicable": "不适用",
                "pending_confirmation": "待确认",
            }
            parameter_labels = {
                "wind_load_pa": "厂家风荷载",
                "front_static_load_pa": "正面最大静载",
                "back_static_load_pa": "背面最大静载",
                "hail_resistance_mm": "冰雹试验直径",
                "hail_impact_velocity_m_s": "冰雹试验速度",
                "snow_load_pa": "厂家雪荷载",
            }
            lines.extend(["### 逐灾种安装参数适用性", ""])
            for review in assessment.installation_parameter_reviews:
                parameters = "、".join(
                    parameter_labels.get(field, field)
                    for field in review.parameter_fields
                )
                requirements = "；".join(review.required_evidence)
                lines.append(
                    f"- {hazard_labels[review.hazard]}："
                    f"{status_labels[review.status.value]}；参数：{_table_cell(parameters)}；"
                    f"原因：{_table_cell(review.explanation)}；"
                    f"需核对：{_table_cell(requirements)}；"
                    f"规则：{review.triggered_rule_id}"
                )
            lines.append("")

    if case.catastrophe_assessment is not None:
        rows = case.catastrophe_assessment.comparisons
        if rows:
            lines.extend(["### 逐项计算明细", "", "| 灾害 | 组件能力 | 历史指标 | 比较需求 | 能力比 | 判断 |", "| --- | --- | --- | --- | --- | --- |"])
            for row in rows:
                label = {"wind":"风灾", "hail":"雹灾", "snow":"雪灾"}[row.hazard]
                state = LOSS_RISK_LABELS[row.risk.value] if row.status == 'calculated' else '数据不足'
                event_unit = 'm/s' if row.hazard == 'wind' else row.unit
                lines.append(f"| {label} | {_display(row.capacity)} {row.unit} | {_display(row.event)} {event_unit} | {_display(row.demand)} {row.unit} | {_display(row.ratio)} | {state} |")
            lines.append("")
            for row in rows:
                label = {"wind":"风灾", "hail":"雹灾", "snow":"雪灾"}[row.hazard]
                lines.append(f"- {label}计算：{_table_cell(row.formula)}；{_table_cell(row.reason) if row.reason else '按保存的输入进行比较'}；规则：{'、'.join(row.rule_ids) or '该项未完成计算'}")
        else:
            lines.append("- 历史记录未保存逐项计算明细；保留原始结论，不用当前规则重新计算。")
        lines.extend(["", "- 筛查结果不代表出险概率、预计赔款或整套电站承载合格。", ""])

    if case.component_profile is not None:
        component = case.component_profile
        lines.extend(
            [
                "### 组件参数来源",
                "",
                (
                    f"- 型号：{_table_cell(component.component_model)}；厂商：{_table_cell(component.manufacturer)}；"
                    f"目录型号匹配参考分：{component.match_confidence:.2f}；"
                    f"市场版本：{_table_cell(component.market_version)}"
                ),
                (
                    f"- 额定功率：{_display_measurement(component.rated_power_w)} W；"
                    f"正面最大静态载荷：{_display_measurement(component.front_static_load_pa)} Pa；"
                    f"背面最大静态载荷：{_display_measurement(component.back_static_load_pa)} Pa"
                ),
                (
                    f"- 厂家冰雹试验：{_display_measurement(component.hail_resistance_mm)} mm；"
                    f"试验冲击速度：{_display_measurement(component.hail_impact_velocity_m_s)} m/s；"
                    f"单独列示的风荷载：{_display_measurement(component.wind_load_pa)} Pa；"
                    f"单独列示的雪荷载：{_display_measurement(component.snow_load_pa)} Pa"
                ),
                (
                    f"- 型号来源方式：{_table_cell(component.model_derivation_method)}；"
                    f"文件类型：{_table_cell(component.source_document_type)}"
                ),
                f"- 厂家参数说明：{_table_cell(component.source_note)}",
                (
                    f"- 来源：{_table_cell(component.source_name)}；"
                    f"链接：{_table_cell(component.source_url)}；获取时间：{component.retrieved_at.isoformat()}"
                ),
                "- 口径边界：正反面最大静载作为厂家参数记录，不折算为项目设计风压或屋面结构雪荷载；参数有值不等于该灾种自动通过。",
                "",
            ]
        )
        if component.parameter_sources:
            labels = {
                "rated_power_w": "额定功率",
                "hail_resistance_mm": "抗冰雹",
                "hail_impact_velocity_m_s": "冰雹试验冲击速度",
                "front_static_load_pa": "正面最大静态载荷",
                "back_static_load_pa": "背面最大静态载荷",
                "wind_load_pa": "风荷载",
                "snow_load_pa": "雪荷载",
            }
            lines.append("- 参数逐项来源：")
            lines.extend(
                f"  - {labels.get(field, field)}：{_table_cell(source)}"
                for field, source in component.parameter_sources.items()
            )
            lines.append("")
        lines.extend(f"- 查询说明：{_table_cell(note)}" for note in component.lookup_notes)

    if case.weather_profile is not None:
        weather = case.weather_profile
        lines.extend(
            [
                "### 气象数据范围",
                "",
                f"- 项目查询坐标（WGS84）：{weather.longitude:.5f}, {weather.latitude:.5f}",
                (
                    f"- 请求期间：{_display(weather.observation_start)} 至 {_display(weather.observation_end)}；"
                    f"上游返回日期：{_display(weather.returned_data_start)} 至 {_display(weather.returned_data_end)}；"
                    f"来源：{_table_cell(weather.source_name)}；链接：{_table_cell(weather.source_url)}"
                ),
                (
                    f"- 阵风有效日数：{_display(weather.wind_valid_day_count)}/"
                    f"{_display(weather.expected_day_count)}，历史最大值："
                    f"{_display_measurement(weather.historical_max_wind_m_s)} {weather.wind_unit or 'm/s'}；"
                    f"日持续风速有效日数：{_display(weather.wind_speed_valid_day_count)}/"
                    f"{_display(weather.expected_day_count)}，历史最大值："
                    f"{_display_measurement(weather.historical_max_daily_wind_speed_m_s)} "
                    f"{weather.wind_speed_unit or 'm/s'}；"
                    f"单日总降水有效日数：{_display(weather.precipitation_valid_day_count)}/"
                    f"{_display(weather.expected_day_count)}，最大值："
                    f"{_display_measurement(weather.historical_max_daily_precipitation_mm)} "
                    f"{weather.precipitation_unit or 'mm'}；"
                    f"单日降雨有效日数：{_display(weather.rain_valid_day_count)}/"
                    f"{_display(weather.expected_day_count)}，最大值："
                    f"{_display_measurement(weather.historical_max_daily_rain_mm)} "
                    f"{weather.rain_unit or 'mm'}；"
                    f"降水时数有效日数：{_display(weather.precipitation_hours_valid_day_count)}/"
                    f"{_display(weather.expected_day_count)}，最长单日有降水时数："
                    f"{_display_measurement(weather.historical_max_daily_precipitation_hours)} "
                    f"{weather.precipitation_hours_unit or 'h'}；"
                    f"降雪有效日数：{_display(weather.snowfall_valid_day_count)}/"
                    f"{_display(weather.expected_day_count)}，历史最大单日降雪："
                    f"{_display_measurement(weather.historical_max_daily_snowfall_cm)} {weather.snowfall_unit or 'cm'}"
                ),
                (
                    f"- 数据集选择：{_table_cell(weather.dataset_selection)}；"
                    f"网格选择：{_table_cell(weather.grid_selection_method)}；"
                    f"时区：{_table_cell(weather.timezone)}；"
                    f"实际气象网格：{_display(weather.grid_longitude)}, {_display(weather.grid_latitude)}；"
                    f"网格距项目点：{_display(weather.grid_distance_km)} km；"
                    f"网格 DEM 高程：{_display(weather.grid_elevation_m)} m"
                ),
                (
                    f"- 当前源未提供可用于量化的历史冰雹直径：{_display(weather.historical_max_hail_mm)} mm；"
                    f"项目规范雪荷载：{_display(weather.historical_max_snow_load_pa)} Pa"
                ),
                "- 资料说明：历史再分析和网格点用于气候背景筛查，不等同于项目现场气象站实测或结构设计参数。",
                "",
            ]
        )
        lines.extend(
            f"- 数据质量提示：{_table_cell(note)}"
            for note in weather.data_quality_notes
        )
        if weather.data_quality_notes:
            lines.append("")

    if case.map_reviews:
        lines.extend(
            [
                "",
                "### 地图影像辅助复核（外部参考）",
                "",
                (
                    "> 地图影像是第三方存档影像，不代表实时现场状态。拍摄日期可能未知；"
                    "位置和可见范围必须由人工核实。此信息不会自动改变核保结论。"
                ),
                "",
            ]
        )
        visibility_labels = {
            "visible": "可见",
            "not_visible": "未见",
            "unclear": "不确定",
        }
        address_source_labels = {
            "project_info": "项目基本信息",
            "material_ocr": "材料文字识别/人工核对",
            "human_corrected": "人工更正",
        }
        for review in case.map_reviews:
            address_match_details = (
                "高德接口未返回可信度评分；已由核保员人工确认候选位置"
                if review.geocoding_confidence is None
                or review.address_comprehension is None
                else (
                    f"匹配度 {review.address_comprehension}/100；"
                    f"定位置信分 {review.geocoding_confidence}/100；"
                    f"精确匹配 {'是' if review.precise_match else '否'}"
                )
            )
            if review.match_level:
                address_match_details += f"；解析级别 {_table_cell(review.match_level)}"
            lines.extend(
                [
                    f"#### 复核记录 {_table_cell(review.review_id)}",
                    "",
                    f"- 地图服务：{_table_cell(review.provider)}；地址来源：{address_source_labels[review.address_source]}",
                    f"- 触发复核的模糊/低质量材料：{_table_cell('、'.join(review.triggering_material_ids))}",
                    f"- 查询地址：{_table_cell(review.query_address)}；匹配地址：{_table_cell(review.matched_address)}",
                    f"- 地址匹配依据：{address_match_details}",
                    (
                        f"- 地图坐标（GCJ-02）：{review.longitude_gcj02}, {review.latitude_gcj02}"
                        if review.provider == "amap_maps"
                        else f"- 地图坐标（BD-09）：{review.longitude_bd09}, {review.latitude_bd09}"
                    ),
                    (
                        f"- 天气查询坐标（WGS84 近似）：{review.longitude_wgs84}, {review.latitude_wgs84}"
                        if review.longitude_wgs84 is not None
                        else "- 天气查询坐标：未记录"
                    ),
                    f"- 地图查看入口：{review.provider_map_url}",
                    f"- 复核人：{_table_cell(review.reviewer_name)}；项目位置确认：{'是' if review.site_match_confirmed else '否'}",
                    (
                        f"- 地图可见光伏组件：{visibility_labels[review.photovoltaic_visibility]}；"
                        f"观察到的安装载体：{INSTALLATION_TYPE_LABELS[review.observed_installation_type]}"
                    ),
                    f"- 影像拍摄日期：{_display(review.imagery_capture_date)}；查询时间：{review.queried_at.isoformat()}；记录时间：{review.reviewed_at.isoformat()}",
                    f"- 人工观察：{_table_cell(review.observations)}",
                    "- 对自动核保结论的作用：仅供人工参考；未作为自动规则事实。",
                    "",
                ]
            )
            if review.sentinel_context:
                context = review.sentinel_context
                cloud = (
                    "unknown"
                    if context.tile_cloud_cover_percent is None
                    else f"{context.tile_cloud_cover_percent:.1f}% (scene/tile estimate)"
                )
                lines.extend(
                    [
                        "##### Sentinel-2 surroundings image",
                        "",
                        f"- Source: Copernicus Sentinel-2 L2A; acquisition: {context.acquired_at.isoformat()}",
                        f"- Scene: {_table_cell(context.scene_id)}; cloud cover: {cloud}; masked pixels: {context.masked_pixel_fraction:.1%}",
                        f"- Scale: about {context.pixel_size_m:.1f} m per pixel; radius: {context.radius_m} m; WGS84 bbox: {context.bbox_wgs84}",
                        f"- Cloud note: {_table_cell(context.tile_cloud_cover_note)}",
                        f"- Attribution: {_table_cell(context.attribution)}",
                    ]
                )
                if context.quality_warning:
                    lines.append(f"- Image quality warning: {_table_cell(context.quality_warning)}")
                if context.analysis_warning:
                    lines.append(f"- VLM warning: {_table_cell(context.analysis_warning)}")
                if context.analysis:
                    lines.append(f"- Optional VLM summary (not an underwriting result): {_table_cell(context.analysis.summary)}")
                    lines.extend(
                        f"  - {item.category} / {item.presence} / confidence {item.confidence:.2f}: {_table_cell(item.evidence)}"
                        for item in context.analysis.observations
                    )
                lines.append("")
    else:
        lines.extend([
"", "### 地图影像辅助复核", "", "- 未执行。", ""])

    lines.extend(
        [
            "",
            "## 7. 处理留痕",
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

    lines.extend(
        [
            "",
            "## 8. 人工复核记录",
            "",
            "| 复核人 | 最终意见 | 复核时间（UTC） | 说明 |",
            "| --- | --- | --- | --- |",
        ]
    )
    review_labels = {
        "accept": "建议承保",
        "recommend_reject": "建议拒保",
        "surcharge": "建议加费",
        "conditional_accept": "附条件承保",
        "request_more": "补充材料",
    }
    if human_reviews:
        for review in human_reviews:
            lines.append(
                "| "
                f"{_table_cell(review.get('reviewer_name'))} | "
                f"{review_labels.get(review.get('final_decision', ''), '未指定')} | "
                f"{_table_cell(review.get('reviewed_at'))} | "
                f"{_table_cell(review.get('comment'))} |"
            )
    else:
        lines.append("| 尚无人复核 | — | — | — |")

    return "\n".join(lines).rstrip() + "\n"
