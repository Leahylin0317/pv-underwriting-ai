from app.contracts import (
    CatastropheAssessment,
    ComponentProfile,
    ExpectedLossRisk,
    ResistanceLevel,
    WeatherProfile,
)
from app.rules.config import BusinessRulesConfig

WIND_PRESSURE_COEFFICIENT = 0.613
ADEQUATE_MARGIN_RATIO = 1.25
CRITICAL_SHORTFALL_RATIO = 0.75


class CatastropheAssessmentEngine:
    """比较组件额定能力与项目所在地历史灾害指标。"""

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
        outcomes: list[tuple[ResistanceLevel, ExpectedLossRisk]] = []

        if component is None:
            missing.append("组件抗灾参数")
            rule_ids.append("CAT-COMPONENT-PROFILE-MISSING")

        if weather is None:
            missing.append("项目所在地历史气象数据")
            rule_ids.append("CAT-WEATHER-PROFILE-MISSING")

        if component is not None and weather is not None:
            if weather.historical_max_daily_snowfall_cm is not None:
                factors.append(
                    "气候背景：历史最大单日降雪量约 "
                    f"{weather.historical_max_daily_snowfall_cm:.1f} cm；"
                    "降雪量未换算为结构雪荷载，不直接用于承载结论"
                )
            self._assess_wind(component, weather, factors, rule_ids, missing, outcomes)
            self._assess_hail(component, weather, factors, rule_ids, missing, outcomes)
            self._assess_snow(component, weather, factors, rule_ids, missing, outcomes)

        resistance, risk = self._aggregate(outcomes, bool(missing))
        requires_manual_review = bool(missing) or risk is not ExpectedLossRisk.LOW

        if missing:
            factors.append("缺少：" + "、".join(missing))

        if missing and risk in {ExpectedLossRisk.HIGH, ExpectedLossRisk.CRITICAL}:
            explanation = "已发现组件能力不足，且部分灾害数据缺失，需要人工复核。"
        elif missing:
            explanation = "部分组件或气象灾害数据缺失，当前无法完成综合抗灾判断。"
        elif risk is ExpectedLossRisk.LOW:
            explanation = "组件风、雹、雪额定能力均通过当前历史数据筛查。"
        elif risk is ExpectedLossRisk.MEDIUM:
            explanation = "组件抗灾能力余量有限，需要人工确认设计条件和安全系数。"
        else:
            explanation = "至少一项历史灾害指标超过组件额定能力，需要人工复核。"

        return CatastropheAssessment(
            comparisons=self.comparisons(component,weather),
            resistance_level=resistance,
            expected_loss_risk=risk,
            factors=factors,
            explanation=explanation,
            triggered_rule_ids=list(dict.fromkeys(rule_ids)),
            requires_manual_review=requires_manual_review,
            critical_shortfall_ratio=self.critical_shortfall_ratio,
            adequate_margin_ratio=self.adequate_margin_ratio,
        )

    def _assess_wind(
        self,
        component: ComponentProfile,
        weather: WeatherProfile,
        factors: list[str],
        rule_ids: list[str],
        missing: list[str],
        outcomes: list[tuple[ResistanceLevel, ExpectedLossRisk]],
    ) -> None:
        if component.wind_load_pa is None or weather.historical_max_wind_m_s is None:
            missing.append("风荷载能力或历史最大阵风")
            rule_ids.append("CAT-WIND-DATA-MISSING")
            return

        demand_pa = WIND_PRESSURE_COEFFICIENT * weather.historical_max_wind_m_s**2
        ratio = component.wind_load_pa / demand_pa if demand_pa > 0 else float("inf")
        factors.append(
            "风灾筛查：组件额定风荷载 "
            f"{component.wind_load_pa:.0f} Pa，历史阵风动压约 {demand_pa:.0f} Pa，"
            f"能力比 {ratio:.2f}"
        )
        self._record_ratio("WIND", ratio, rule_ids, outcomes)

    def _assess_hail(
        self,
        component: ComponentProfile,
        weather: WeatherProfile,
        factors: list[str],
        rule_ids: list[str],
        missing: list[str],
        outcomes: list[tuple[ResistanceLevel, ExpectedLossRisk]],
    ) -> None:
        if component.hail_resistance_mm is None or weather.historical_max_hail_mm is None or weather.historical_max_hail_mm <= 0:
            missing.append("冰雹抗性或历史最大冰雹直径")
            rule_ids.append("CAT-HAIL-DATA-MISSING")
            return

        ratio = component.hail_resistance_mm / weather.historical_max_hail_mm
        factors.append(
            "雹灾筛查：组件抗冰雹直径 "
            f"{component.hail_resistance_mm:.1f} mm，历史最大冰雹 "
            f"{weather.historical_max_hail_mm:.1f} mm，能力比 {ratio:.2f}"
        )
        self._record_ratio("HAIL", ratio, rule_ids, outcomes)

    def _assess_snow(
        self,
        component: ComponentProfile,
        weather: WeatherProfile,
        factors: list[str],
        rule_ids: list[str],
        missing: list[str],
        outcomes: list[tuple[ResistanceLevel, ExpectedLossRisk]],
    ) -> None:
        if component.snow_load_pa is None or weather.historical_max_snow_load_pa is None or weather.historical_max_snow_load_pa <= 0:
            missing.append("雪荷载能力或历史最大雪荷载")
            rule_ids.append("CAT-SNOW-DATA-MISSING")
            return

        ratio = component.snow_load_pa / weather.historical_max_snow_load_pa
        factors.append(
            "雪灾筛查：组件额定雪荷载 "
            f"{component.snow_load_pa:.0f} Pa，历史最大雪荷载 "
            f"{weather.historical_max_snow_load_pa:.0f} Pa，能力比 {ratio:.2f}"
        )
        self._record_ratio("SNOW", ratio, rule_ids, outcomes)

    def _record_ratio(
        self,
        hazard: str,
        ratio: float,
        rule_ids: list[str],
        outcomes: list[tuple[ResistanceLevel, ExpectedLossRisk]],
    ) -> None:
        if ratio < self.critical_shortfall_ratio:
            rule_ids.append(f"CAT-{hazard}-CRITICAL")
            outcomes.append((ResistanceLevel.LOW, ExpectedLossRisk.CRITICAL))
        elif ratio < 1.0:
            rule_ids.append(f"CAT-{hazard}-CAPACITY-SHORTFALL")
            outcomes.append((ResistanceLevel.LOW, ExpectedLossRisk.HIGH))
        elif ratio < self.adequate_margin_ratio:
            rule_ids.append(f"CAT-{hazard}-LIMITED-MARGIN")
            outcomes.append((ResistanceLevel.MEDIUM, ExpectedLossRisk.MEDIUM))
        else:
            rule_ids.append(f"CAT-{hazard}-CAPACITY-ADEQUATE")
            outcomes.append((ResistanceLevel.HIGH, ExpectedLossRisk.LOW))

    @staticmethod
    def _aggregate(
        outcomes: list[tuple[ResistanceLevel, ExpectedLossRisk]],
        has_missing_data: bool,
    ) -> tuple[ResistanceLevel, ExpectedLossRisk]:
        risks = [risk for _, risk in outcomes]

        if ExpectedLossRisk.CRITICAL in risks:
            return ResistanceLevel.LOW, ExpectedLossRisk.CRITICAL
        if ExpectedLossRisk.HIGH in risks:
            return ResistanceLevel.LOW, ExpectedLossRisk.HIGH
        if has_missing_data:
            return ResistanceLevel.UNKNOWN, ExpectedLossRisk.UNKNOWN
        if ExpectedLossRisk.MEDIUM in risks:
            return ResistanceLevel.MEDIUM, ExpectedLossRisk.MEDIUM
        if risks:
            return ResistanceLevel.HIGH, ExpectedLossRisk.LOW
        return ResistanceLevel.UNKNOWN, ExpectedLossRisk.UNKNOWN

    def comparisons(self, component, weather):
        """Expose numerical screening evidence; zero demand is explicit, never Infinity in JSON."""
        rows=[]
        for hazard,capacity_key,event_key,unit in [('WIND','wind_load_pa','historical_max_wind_m_s','Pa'),('HAIL','hail_resistance_mm','historical_max_hail_mm','mm'),('SNOW','snow_load_pa','historical_max_snow_load_pa','Pa')]:
            capacity=getattr(component,capacity_key,None)
            event=getattr(weather,event_key,None)
            demand=WIND_PRESSURE_COEFFICIENT*event**2 if hazard=='WIND' and event is not None else event
            usable=capacity is not None and demand is not None and (demand>0 or hazard=='WIND')
            ratio=capacity/demand if usable and demand>0 else None
            outcome=[];rules=[]
            if usable:self._record_ratio(hazard,ratio if ratio is not None else float('inf'),rules,outcome)
            reason=''
            if not usable:reason='缺少组件能力或灾害指标' if capacity is None or demand is None else '指标为0，未取得可用于比较的正值'
            elif demand==0:reason='所选历史范围阵风为0；未形成正值比较需求，不能外推项目安全性'
            rows.append({'hazard':hazard.lower(),'capacity':capacity,'event':event,'demand':demand,'unit':unit,'ratio':ratio,
                         'status':'calculated' if usable else 'insufficient','risk':outcome[0][1].value if outcome else 'unknown',
                         'rule_ids':rules,'reason':reason,'formula':'0.613 × 最大阵风²；能力 ÷ 动压' if hazard=='WIND' else '组件能力 ÷ 历史灾害指标'})
        return rows
