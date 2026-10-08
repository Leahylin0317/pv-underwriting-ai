"""Human-readable explanations for deterministic underwriting rule IDs."""

from app.contracts import RuleExplanation

_RULES: dict[str, tuple[str, str, str]] = {
    "LOC-CONFLICT-001": (
        "材料位置冲突",
        "独立材料的电站地址或现场坐标明显不一致。",
        "暂停自动通过，核对原件和照片；确认异地前不自动拒保。",
    ),
    "LOC-SINGLE-SOURCE-001": (
        "位置只有一个来源",
        "只有一份独立材料提供可用的电站位置，不能交叉核验。",
        "要求补充第二份独立位置材料；天气查询结果只作未经核实的候选参考。",
    ),
    "LOC-UNCERTAIN-001": (
        "项目位置待核实",
        "位置缺失、地址定位不够精确或材料尚不能可靠比较。",
        "补充精确材料或转人工核对，不把不确定当作通过或拒保。",
    ),
    "PKG-MINIMUM-001": (
        "投保材料包不完整",
        "图片数量、全景视角或必需文件未达到当前配置的最低要求。",
        "要求补充材料；补齐前不把缺失信息当作风险已排除。",
    ),
    "ENV-EXCLUDED-001": (
        "发现拒保候选环境",
        "全景或屋顶连接材料识别到拒保环境，环境关系属于已配置的拒保范围、参考置信度达到配置门槛且模型未要求人工复核。",
        "生成拒保建议，并展示现场关系、原图证据和参考置信度。",
    ),
    "ENV-COVERAGE-001": (
        "环境检查覆盖不足",
        "合并所有全景照片后，必检类别在全部视角中都没有识别记录或只被标记为不适用。",
        "仅对未覆盖的类别提出针对性补充视角，或由核保人员记录检查结果。",
    ),
    "ENV-SITE-RELATION-REVIEW-001": (
        "拒保环境与现场关系待核",
        "环境可能存在，但位于项目周边、模型要求人工复核、置信度不足或无法确认是否属于项目现场。",
        "保留证据并转人工核验；在现场关系确认前不自动拒保，也不单凭该项要求补件。",
    ),
    "ENV-BACKGROUND-CONTEXT-001": (
        "拒保环境仅作为远处背景",
        "识别到的环境被标记为远处背景景物，不属于当前项目现场。",
        "保留识别结果供查看，但不触发现场拒保或人工复核。",
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
        "按赛题首期规则提示建议补充带水印照片；无水印本身不升级为强制补材。",
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
    "CAT-WIND-COMPARABILITY-UNVERIFIED": (
        "风灾数据口径未验证",
        "历史10米阵风、当地设计风压和组件厂家载荷试验不是可直接互换的指标。",
        "不计算风灾能力比，转人工核验设计风荷载、安装条件和厂家试验口径。",
    ),
    "CAT-HAIL-DATA-MISSING": (
        "雹灾比较数据不完整",
        "组件抗雹能力或历史最大冰雹直径数据缺失。",
        "不生成完整雹灾比较，转人工核实。",
    ),
    "CAT-HAIL-COMPONENT-DATA-MISSING": (
        "缺少厂家冰雹试验参数",
        "组件目录没有可核验的厂家冰雹冲击试验记录。",
        "保留未知状态，转人工核验规格书。",
    ),
    "CAT-HAIL-WEATHER-DATA-MISSING": (
        "缺少历史冰雹事件资料",
        "当前气象 Provider 没有提供项目所在地可靠的历史冰雹事件记录。",
        "不推断冰雹安全，转人工复核。",
    ),
    "CAT-HAIL-COMPARABILITY-UNVERIFIED": (
        "雹灾数据口径未验证",
        "厂家抗雹试验包含粒径和冲击条件，气象最大直径不能单独代表可配对事件。",
        "不计算雹灾能力比，转人工核验试验标准和同口径事件数据。",
    ),
    "CAT-SNOW-DATA-MISSING": (
        "雪灾比较数据不完整",
        "组件雪荷载能力或历史最大雪荷载数据缺失。",
        "不生成完整雪灾比较，转人工核实。",
    ),
    "CAT-SNOW-COMPONENT-DATA-MISSING": (
        "缺少组件雪荷载试验参数",
        "组件目录没有可核验的厂家雪荷载试验参数。",
        "保留未知状态，转人工核验规格书和安装方式。",
    ),
    "CAT-SNOW-WEATHER-DATA-MISSING": (
        "缺少项目规范雪荷载",
        "历史降雪量不是屋面结构设计雪荷载，当前没有适用的项目规范雪荷载。",
        "不把降雪量换算成雪荷载，转人工核对当地规范设计值。",
    ),
    "CAT-SNOW-COMPARABILITY-UNVERIFIED": (
        "雪灾数据口径未验证",
        "厂家组件载荷与屋面结构雪荷载需结合试验定义、安装方式和设计条件解释。",
        "不计算雪灾能力比，转人工核验结构设计与厂家允许条件。",
    ),
    "CAT-INSTALL-WIND-APPLICABILITY-PENDING": (
        "大风参数安装适用性待确认",
        "尚无证据证明项目组件固定方式、固定边、固定点、夹持位置和支撑条件符合厂家对应抗风配置。",
        "补充精确型号/版本、厂家配置编号和现场安装证据；确认前不使用该参数定级。",
    ),
    "CAT-INSTALL-HAIL-APPLICABILITY-PENDING": (
        "冰雹参数试验适用性待确认",
        "厂家冰雹试验记录尚未与精确型号、资料版本、试验方法和可比历史事件口径一并核实。",
        "补充厂家 Datasheet/检测报告及试验条件；可比数据未满足前不生成历史筛查等级。",
    ),
    "CAT-INSTALL-SNOW-APPLICABILITY-PENDING": (
        "积雪参数安装适用性待确认",
        "尚无证据证明厂家承载参数适用于项目固定配置，也未提供可与之同单位同定义的屋面设计雪荷载。",
        "补充安装配置、支架/屋面承载资料和同口径雪荷载；确认前不使用静载或降雪量推断结构能力。",
    ),
}

_HAZARD_LABELS = {"WIND": "风灾", "HAIL": "雹灾", "SNOW": "雪灾"}
_CAT_OUTCOMES = {
    "CRITICAL": ("历史筛查判为严重不足", "旧版演示逻辑按未经业务确认的能力比阈值分类。", "保留历史规则结果；不代表已完成工程验算，需人工复核。"),
    "CAPACITY-SHORTFALL": ("历史筛查判为能力不足", "旧版演示逻辑按未经业务确认的能力比阈值分类。", "保留历史规则结果；不代表已完成工程验算，需人工复核。"),
    "LIMITED-MARGIN": ("历史筛查判为余量有限", "旧版演示逻辑按未经业务确认的能力比阈值分类。", "保留历史规则结果；不代表已完成工程验算，需人工复核。"),
    "CAPACITY-ADEQUATE": ("历史简化筛查结果", "旧版演示逻辑曾将能力比达到配置阈值记为单项通过。", "仅保留历史结果；不代表结构安全结论或承保审批。"),
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
