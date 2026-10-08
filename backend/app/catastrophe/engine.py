from app.rules.config import BusinessRulesConfig

from app.contracts import (
    CatastropheAssessment,
    ComponentProfile,
    ExpectedLossRisk,
    InstallationParameterReview,
    ParameterApplicabilityStatus,
    ResistanceLevel,
    WeatherProfile,
)


class CatastropheAssessmentEngine:
    """Summarize source evidence without comparing unlike engineering quantities."""

    def __init__(self, config: BusinessRulesConfig | None = None) -> None:
        rules = config or BusinessRulesConfig.load()
        self.adequate_margin_ratio = rules.catastrophe_adequate_margin_ratio
        self.critical_shortfall_ratio = rules.catastrophe_critical_shortfall_ratio

    def assess(
        self,
        *,
        component: ComponentProfile | None,
        weather: WeatherProfile | None,
    ) -> CatastropheAssessment:
        factors: list[str] = []
        rule_ids: list[str] = []
        missing: list[str] = []
        installation_reviews = self._installation_reviews()
        rule_ids.extend(review.triggered_rule_id for review in installation_reviews)
        missing.append("组件灾害参数与现场安装配置的逐项适用性证据")

        if component is None:
            missing.append("可核验的组件型号及厂家参数")
            rule_ids.append("CAT-COMPONENT-PROFILE-MISSING")
        if weather is None:
            missing.append("项目所在地历史气象资料")
            rule_ids.append("CAT-WEATHER-PROFILE-MISSING")

        if component is not None and weather is not None:
            self._assess_wind(component, weather, factors, rule_ids, missing)
            self._assess_hail(component, weather, factors, rule_ids, missing)
            self._assess_snow(component, weather, factors, rule_ids, missing)

        if missing:
            factors.append("人工复核事项：" + "；".join(dict.fromkeys(missing)))

        factors.append(
            "安装参数适用性待确认：组件型号参数尚未与厂家手册中的固定方式、固定边、固定点、"
            "夹持位置和支撑条件逐项匹配；未知条件不会按满足处理。"
        )

        # Keep the raw numbers visible in the case report while withholding
        # a ratio verdict until weather, engineering and mounting conditions
        # have been shown to be comparable.
        comparisons = [
            {
                **row,
                "ratio": None,
                "status": "insufficient",
                "risk": ExpectedLossRisk.UNKNOWN.value,
                "rule_ids": [],
                "reason": "安装条件与灾害指标口径尚未核验，不能作为核保能力比",
            }
            for row in self.comparisons(component, weather)
        ]
        return CatastropheAssessment(
            comparisons=comparisons,
            resistance_level=ResistanceLevel.UNKNOWN,
            expected_loss_risk=ExpectedLossRisk.UNKNOWN,
            factors=factors,
            explanation=(
                "目前没有经核验的厂家安装配置证据，也没有可与组件参数逐年比较的同口径风、雹、雪历史序列；"
                "系统不生成 A/B/C 或 R1/R2/R3 候选等级，也不计算真实出险概率。请先核对精确型号、"
                "厂家手册版本、安装配置和对应证据，再补齐可比历史数据。未知表示尚不能评估，不表示已经通过或超限。"
            ),
            triggered_rule_ids=list(dict.fromkeys(rule_ids)),
            requires_manual_review=True,
            installation_parameter_reviews=installation_reviews,
            critical_shortfall_ratio=None,
            adequate_margin_ratio=None,
        )

    @staticmethod
    def _installation_reviews() -> list[InstallationParameterReview]:
        """The supplied installation scheme requires evidence absent from each case."""

        pending = ParameterApplicabilityStatus.PENDING_CONFIRMATION
        return [
            InstallationParameterReview(
                hazard="wind",
                parameter_fields=[
                    "wind_load_pa",
                    "front_static_load_pa",
                    "back_static_load_pa",
                ],
                status=pending,
                explanation=(
                    "缺少精确型号对应的厂家抗风配置及现场安装事实；静态载荷参数不能直接代表项目设计风压。"
                ),
                required_evidence=[
                    "型号、后缀、规格书/安装手册版本及配置编号",
                    "组件固定方式、固定边、固定点数量、夹持位置、导轨方向和支撑条件",
                    "可定位的近照、厂家安装图或安装验收记录；照片无法证明的隐蔽连接转人工核验",
                ],
                triggered_rule_id="CAT-INSTALL-WIND-APPLICABILITY-PENDING",
            ),
            InstallationParameterReview(
                hazard="hail",
                parameter_fields=["hail_resistance_mm", "hail_impact_velocity_m_s"],
                status=pending,
                explanation=(
                    "缺少与精确型号、规格书版本及试验方法绑定的厂家冰雹测试依据；"
                    "试验参数还不能与当前历史天气源同口径比较。"
                ),
                required_evidence=[
                    "精确型号对应的厂家 Datasheet/检测报告及版本",
                    "冰雹直径、冲击速度、试验方法和适用范围",
                    "可用于逐年比较的当地历史冰雹事件数据及其统计口径",
                ],
                triggered_rule_id="CAT-INSTALL-HAIL-APPLICABILITY-PENDING",
            ),
            InstallationParameterReview(
                hazard="snow",
                parameter_fields=[
                    "snow_load_pa",
                    "front_static_load_pa",
                    "back_static_load_pa",
                ],
                status=pending,
                explanation=(
                    "缺少与实际固定配置对应的厂家承载参数及屋面结构设计雪荷载；"
                    "降雪量或组件静载不能相互换算。"
                ),
                required_evidence=[
                    "精确型号、厂家安装配置编号、受力方向及固定条件",
                    "屋面/支架承载设计或检测、验收资料",
                    "与厂家能力同单位、同定义的项目历史/设计雪荷载数据",
                ],
                triggered_rule_id="CAT-INSTALL-SNOW-APPLICABILITY-PENDING",
            ),
        ]

    @staticmethod
    def _assess_wind(
        component: ComponentProfile,
        weather: WeatherProfile,
        factors: list[str],
        rule_ids: list[str],
        missing: list[str],
    ) -> None:
        if weather.historical_max_wind_m_s is None:
            missing.append("历史最大阵风")
            rule_ids.append("CAT-WIND-DATA-MISSING")
        else:
            factors.append(
                "风灾气象背景：历史最大10米阵风 "
                f"{weather.historical_max_wind_m_s:.1f} m/s"
                f"（{weather.source_name}；再分析资料）"
            )
        if weather.historical_max_daily_wind_speed_m_s is not None:
            factors.append(
                "风灾气候背景：历史最大10米日持续风速 "
                f"{weather.historical_max_daily_wind_speed_m_s:.1f} m/s；"
                "该值不等于项目规范设计风速或设计风压"
            )
        if weather.historical_max_daily_precipitation_mm is not None:
            factors.append(
                "降水背景：历史最大单日总降水 "
                f"{weather.historical_max_daily_precipitation_mm:.1f} mm"
                + (
                    f"，最大单日降雨 {weather.historical_max_daily_rain_mm:.1f} mm"
                    if weather.historical_max_daily_rain_mm is not None
                    else ""
                )
                + "；仅作气候背景，不单独推出内涝/洪水风险结论"
            )
        if weather.historical_max_daily_precipitation_hours is not None:
            factors.append(
                "历史最长单日有降水时数 "
                f"{weather.historical_max_daily_precipitation_hours:.1f} h；"
                "不替代排水条件和洪水风险资料"
            )

        if component.wind_load_pa is not None:
            factors.append(f"组件目录另有风荷载字段 {component.wind_load_pa:.0f} Pa，需核对试验口径")
        if (
            component.front_static_load_pa is not None
            or component.back_static_load_pa is not None
        ):
            factors.append(
                "厂家正面/背面最大静态载荷只作为组件试验参数展示，"
                "不会换算成项目设计风压"
            )

        factors.append(
            "风灾未计算能力比：10米历史阵风不是屋面项目设计风压；"
            "还需当地规范风荷载、地形/高度、阵风和体型系数、组件安装及支架条件"
        )
        rule_ids.append("CAT-WIND-COMPARABILITY-UNVERIFIED")
        missing.append("经核验的项目设计风压与组件安装/试验口径")

    @staticmethod
    def _assess_hail(
        component: ComponentProfile,
        weather: WeatherProfile,
        factors: list[str],
        rule_ids: list[str],
        missing: list[str],
    ) -> None:
        if component.hail_resistance_mm is not None:
            impact = (
                f" @ {component.hail_impact_velocity_m_s:.1f} m/s"
                if component.hail_impact_velocity_m_s is not None
                else "（厂家试验速度未记录）"
            )
            factors.append(
                f"组件厂家冰雹试验记录：{component.hail_resistance_mm:.1f} mm{impact}"
            )
        else:
            missing.append("组件厂家冰雹试验参数")
            rule_ids.append("CAT-HAIL-COMPONENT-DATA-MISSING")

        if weather.historical_max_hail_mm is None:
            missing.append("可靠的当地历史冰雹事件数据")
            rule_ids.append("CAT-HAIL-WEATHER-DATA-MISSING")
        else:
            factors.append(
                f"气象源报告历史最大冰雹直径 {weather.historical_max_hail_mm:.1f} mm；"
                "该单一数值不含与厂家试验可配对的冲击速度和事件方法"
            )

        factors.append(
            "冰雹未计算能力比：厂家冲击试验点不能只按直径与气象最大直径直接比较"
        )
        rule_ids.append("CAT-HAIL-COMPARABILITY-UNVERIFIED")
        missing.append("同一冰雹事件的直径、冲击条件及厂家试验标准")

    @staticmethod
    def _assess_snow(
        component: ComponentProfile,
        weather: WeatherProfile,
        factors: list[str],
        rule_ids: list[str],
        missing: list[str],
    ) -> None:
        if weather.historical_max_daily_snowfall_cm is not None:
            factors.append(
                "气候背景：历史最大单日降雪量约 "
                f"{weather.historical_max_daily_snowfall_cm:.1f} cm；"
                "降雪量不换算为屋面或组件结构雪荷载"
            )

        if component.snow_load_pa is not None:
            factors.append(
                f"组件目录另有雪荷载字段 {component.snow_load_pa:.0f} Pa，需核对厂家试验定义"
            )
        else:
            missing.append("适用的组件雪荷载试验参数")
            rule_ids.append("CAT-SNOW-COMPONENT-DATA-MISSING")

        if weather.historical_max_snow_load_pa is None:
            missing.append("项目所在地规范雪荷载/结构设计参数")
            rule_ids.append("CAT-SNOW-WEATHER-DATA-MISSING")
        else:
            factors.append(
                f"气象源提供雪荷载值 {weather.historical_max_snow_load_pa:.0f} Pa，"
                "仍需确认其是否为项目所在地规范设计值"
            )

        if (
            component.front_static_load_pa is not None
            or component.back_static_load_pa is not None
        ):
            factors.append(
                "厂家正面/背面最大静态载荷不是屋面设计雪荷载，系统不作换算"
            )

        factors.append(
            "雪灾未计算能力比：须由屋面结构设计雪荷载、组件安装方式和厂家允许荷载共同确认"
        )
        rule_ids.append("CAT-SNOW-COMPARABILITY-UNVERIFIED")
        missing.append("经核验的屋面规范雪荷载与组件安装条件")

    def comparisons(
        self,
        component: ComponentProfile | None,
        weather: WeatherProfile | None,
    ) -> list[dict]:
        """Experimental numerical screen for the risk laboratory only.

        These ratios do not establish an underwriting grade or replace the
        installation and engineering comparability checks in ``assess``.
        """
        rows = []
        for hazard, capacity_field, event_field, unit in (
            ("wind", "wind_load_pa", "historical_max_wind_m_s", "Pa"),
            ("hail", "hail_resistance_mm", "historical_max_hail_mm", "mm"),
            ("snow", "snow_load_pa", "historical_max_snow_load_pa", "Pa"),
        ):
            capacity = getattr(component, capacity_field, None)
            event = getattr(weather, event_field, None)
            demand = 0.613 * event**2 if hazard == "wind" and event is not None else event
            ratio = capacity / demand if capacity is not None and demand is not None and demand > 0 else None
            if ratio is None:
                risk = ExpectedLossRisk.UNKNOWN
                rule_ids: list[str] = []
                reason = "缺少可比较的正值；安装和数据口径也需人工核验"
            elif ratio < self.critical_shortfall_ratio:
                risk = ExpectedLossRisk.CRITICAL
                rule_ids = [f"CAT-{hazard.upper()}-CRITICAL"]
                reason = "仅供实验室筛查，不能直接用于核保结论"
            elif ratio < 1:
                risk = ExpectedLossRisk.HIGH
                rule_ids = [f"CAT-{hazard.upper()}-CAPACITY-SHORTFALL"]
                reason = "仅供实验室筛查，不能直接用于核保结论"
            elif ratio < self.adequate_margin_ratio:
                risk = ExpectedLossRisk.MEDIUM
                rule_ids = [f"CAT-{hazard.upper()}-LIMITED-MARGIN"]
                reason = "仅供实验室筛查，不能直接用于核保结论"
            else:
                risk = ExpectedLossRisk.LOW
                rule_ids = [f"CAT-{hazard.upper()}-CAPACITY-ADEQUATE"]
                reason = "仅供实验室筛查，不能直接用于核保结论"
            rows.append({
                "hazard": hazard, "capacity": capacity, "event": event,
                "demand": demand, "unit": unit, "ratio": ratio,
                "status": "calculated" if ratio is not None else "insufficient",
                "risk": risk.value, "rule_ids": rule_ids, "reason": reason,
                "formula": "0.613 × 最大阵风²；能力 ÷ 动压" if hazard == "wind"
                           else "组件能力 ÷ 历史灾害指标",
            })
        return rows
