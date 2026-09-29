"""Human-readable explanations for deterministic underwriting rule IDs."""

from app.contracts import RuleExplanation

_RULES: dict[str, tuple[str, str, str]] = {
    "PKG-MINIMUM-001": (
        "投保材料包不完整",
        "图片数量、全景视角或必需文件未达到当前配置的最低要求。",
        "要求补充材料；补齐前不把缺失信息当作风险已排除。",
    ),
    "ENV-EXCLUDED-001": (
        "发现拒保候选环境",
        "全景或屋顶连接材料中的相关风险识别命中当前配置的拒保环境类别。",
        "该材料建议拒保，并保留模型证据供核保人复核。",
    ),
    "ENV-COVERAGE-001": (
        "环境检查覆盖不足",
        "关键环境类别未被清晰材料覆盖，或模型对相关环境给出不确定结果。",
        "要求补充可核验的现场全景或由人工完成检查。",
    ),
    "DOC-FILING-EXCLUDED-001": (
        "备案材料命中限制行业关键词",
        "备案材料识别出的行业或经营内容命中当前配置的限制项。",
        "将材料升级为拒保候选；需核对原文和正式业务清单。",
    ),
    "DOC-CROSS-CHECK-001": (
        "材料信息交叉核对不一致",
        "OCR 识别内容与用户录入信息或其他材料之间存在不一致。",
        "标记差异并要求核保人核对原始材料，不自动选择其中一方。",
    ),
    "DOC-REQUIRED-FIELDS-001": (
        "关键文档字段缺失或识别不可靠",
        "必需字段缺失，或识别状态、置信度未达到当前程序门槛。",
        "要求补充清晰材料；低置信度字段不会被默认为已核实。",
    ),
    "MAT-QUALITY-001": (
        "材料质量不足",
        "文件无法可靠读取，或图像质量检查/视觉检查认为关键区域不清晰。",
        "要求重新上传清晰、完整且包含关键区域的材料。",
    ),
    "IMG-WATERMARK-001": (
        "全景照片水印未确认",
        "全景照片未能确认包含可核验的日期和经纬度水印。",
        "要求补充带有完整水印的现场照片。",
    ),
    "IMG-WATERMARK-DATE-001": (
        "全景照片水印信息或时效不满足",
        "水印日期/坐标缺失，起保日期无法用于校验，或照片不在拟起保日前 15 日内。",
        "要求补充有效水印或时效符合要求的全景照片。",
    ),
    "IMG-FINDING-WARNING-001": (
        "图片发现需要人工确认的事项",
        "图像识别发现风险、返回不确定结果，或明确要求人工复核。",
        "保留风险证据并转核保人确认，不把模型描述当作已证实事实。",
    ),
    "IMG-SHADING-SEVERE-001": (
        "严重遮挡候选",
        "图像检查将遮挡识别为严重遮挡类别。",
        "该材料建议拒保；请结合关联图片证据复核。",
    ),
    "ELEC-UNPROTECTED-CABLE-REJECT-001": (
        "发现无保护裸露电缆候选",
        "图像检查将电缆识别为裸露且无保护。",
        "该材料建议拒保；请核对原图和适用业务规则。",
    ),
    "DISC-MONITORING-REVIEW-001": (
        "监控优惠资格待核实",
        "材料提及或显示监控系统，但当前材料不足以确认覆盖、在线状态和正式优惠条件。",
        "转人工核验；系统不根据该规则自动计算或承诺折扣。",
    ),
    "INDUSTRY-FIRE-RULES-UNCONFIGURED-001": (
        "高火险行业规则清单未配置",
        "行业规则清单为空或未配置，系统无法确认该行业是否适用相关要求。",
        "转人工核实行业分类及正式规则，不自动推定通过。",
    ),
    "REQ-PROJECT-COORDINATES": (
        "项目坐标缺失",
        "项目经纬度未提供，无法查询项目所在地历史气象数据。",
        "要求补充准确经纬度后再完成灾害风险评估。",
    ),
    "REQ-COMPONENT-MODEL": (
        "组件型号缺失",
        "未提供完整组件型号，无法匹配抗风、抗雹和雪荷载参数。",
        "要求补充组件型号；匹配不到参数时仍需人工确认。",
    ),
    "SYS-PROVIDER-FAILURE": (
        "自动识别服务未完整执行",
        "处理留痕中存在失败或部分成功步骤。",
        "将案件转人工复核，并在处理记录中展示失败步骤和错误信息。",
    ),
    "CAT-COMPONENT-PROFILE-MISSING": (
        "缺少组件抗灾参数",
        "没有取得用于比较的组件额定抗风、抗雹或雪荷载参数。",
        "灾害风险结论标为不完整并转人工核实。",
    ),
    "CAT-WEATHER-PROFILE-MISSING": (
        "缺少项目气象数据",
        "没有取得项目所在地的历史灾害指标。",
        "灾害风险结论标为不完整并转人工核实。",
    ),
    "CAT-WIND-DATA-MISSING": (
        "风灾比较数据不完整",
        "组件风荷载能力或历史最大阵风数据缺失。",
        "不生成完整风灾比较，转人工核实。",
    ),
    "CAT-HAIL-DATA-MISSING": (
        "雹灾比较数据不完整",
        "组件抗雹能力或历史最大冰雹直径数据缺失。",
        "不生成完整雹灾比较，转人工核实。",
    ),
    "CAT-SNOW-DATA-MISSING": (
        "雪灾比较数据不完整",
        "组件雪荷载能力或历史最大雪荷载数据缺失。",
        "不生成完整雪灾比较，转人工核实。",
    ),
}

_HAZARD_LABELS = {"WIND": "风灾", "HAIL": "雹灾", "SNOW": "雪灾"}
_CAT_OUTCOMES = {
    "CRITICAL": ("能力严重不足", "能力比落入当前配置的严重不足区间。", "标记为严重风险并转人工复核。"),
    "CAPACITY-SHORTFALL": ("额定能力不足", "能力比低于 1，额定能力低于对应历史指标。", "标记为高风险并转人工复核。"),
    "LIMITED-MARGIN": ("安全余量有限", "能力比不低于 1，但低于当前配置的充足余量门槛。", "标记为中等风险并要求人工确认设计条件。"),
    "CAPACITY-ADEQUATE": ("当前指标筛查通过", "能力比达到当前配置的充足余量门槛。", "该单项筛查通过；不代表替代工程鉴定或承保审批。"),
}


def explain_rule(rule_id: str) -> RuleExplanation:
    """Return a user-facing explanation, including an explicit fallback."""
    details = _RULES.get(rule_id)
    if details is None and rule_id.startswith("CAT-"):
        parts = rule_id.split("-", maxsplit=2)
        if len(parts) == 3 and parts[1] in _HAZARD_LABELS:
            outcome = _CAT_OUTCOMES.get(parts[2])
            if outcome is not None:
                hazard = _HAZARD_LABELS[parts[1]]
                title, trigger, effect = outcome
                details = (f"{hazard}{title}", trigger, effect)
    if details is None:
        details = (
            "规则说明待补充",
            "当前结果引用了尚未登记中文说明的规则编号。",
            "保留该编号和原始判断依据；维护规则目录后应补齐说明。",
        )
    title, trigger, effect = details
    return RuleExplanation(rule_id=rule_id, title=title, trigger=trigger, effect=effect)


def explain_rules(rule_ids: list[str]) -> list[RuleExplanation]:
    """Explain rule IDs once each while preserving their original order."""
    return [explain_rule(rule_id) for rule_id in dict.fromkeys(rule_ids)]
