from datetime import UTC, datetime
from time import perf_counter_ns

from app.catastrophe import CatastropheAssessmentEngine
from app.contracts import (
    CatastropheAssessment,
    ComponentProfile,
    Material,
    MaterialReview,
    OcrField,
    ProcessingStatus,
    ProcessingStep,
    ProcessingTrace,
    ProjectInfo,
    RiskFinding,
    UnderwritingCase,
    UnderwritingDecision,
    WeatherProfile,
)
from app.decision import DecisionEngine
from app.providers import MaterialInput, OcrProvider, ProviderError, VisionProvider
from app.providers.component import ComponentProvider
from app.providers.weather import WeatherProvider
from app.rules import RuleEngine


def processing_status(total: int, failures: int) -> ProcessingStatus:
    """根据 Provider 调用失败数量生成处理状态。"""

    if failures == 0:
        return ProcessingStatus.SUCCESS
    if total > 0 and failures == total:
        return ProcessingStatus.FAILED
    return ProcessingStatus.PARTIAL


class UnderwritingPipeline:
    """协调 Provider、灾害评估、规则引擎和决策引擎。"""

    def __init__(
        self,
        ocr_provider: OcrProvider,
        vision_provider: VisionProvider,
        component_provider: ComponentProvider | None = None,
        weather_provider: WeatherProvider | None = None,
        catastrophe_engine: CatastropheAssessmentEngine | None = None,
        rule_engine: RuleEngine | None = None,
        decision_engine: DecisionEngine | None = None,
    ) -> None:
        self.ocr_provider = ocr_provider
        self.vision_provider = vision_provider
        self.component_provider = component_provider
        self.weather_provider = weather_provider
        self.catastrophe_engine = catastrophe_engine
        self.rule_engine = RuleEngine() if rule_engine is None else rule_engine
        self.decision_engine = DecisionEngine() if decision_engine is None else decision_engine

    def run(
        self,
        *,
        case_id: str,
        project: ProjectInfo,
        materials: list[MaterialInput],
    ) -> UnderwritingCase:
        material_models = [item.material for item in materials]
        ocr_fields, ocr_trace = self._run_ocr(materials)
        findings, vision_trace = self._run_vision(materials)

        component_profile: ComponentProfile | None = None
        weather_profile: WeatherProfile | None = None
        catastrophe_assessment: CatastropheAssessment | None = None
        processing_traces = [ocr_trace, vision_trace]

        if self.component_provider is not None:
            component_profile, component_trace = self._run_component_lookup(project)
            processing_traces.append(component_trace)

        if (
            self.weather_provider is not None
            and project.longitude is not None
            and project.latitude is not None
        ):
            weather_profile, weather_trace = self._run_weather_lookup(project)
            processing_traces.append(weather_trace)

        if self.catastrophe_engine is not None:
            catastrophe_assessment, catastrophe_trace = self._run_catastrophe_assessment(
                component_profile,
                weather_profile,
            )
            processing_traces.append(catastrophe_trace)

        material_reviews, rule_trace = self._run_rules(material_models)
        processing_traces.append(rule_trace)

        case_without_decision = UnderwritingCase(
            schema_version="0.1.0",
            case_id=case_id,
            project=project,
            materials=material_models,
            ocr_fields=ocr_fields,
            findings=findings,
            component_profile=component_profile,
            weather_profile=weather_profile,
            catastrophe_assessment=catastrophe_assessment,
            material_reviews=material_reviews,
            decision=None,
            processing_trace=processing_traces,
        )

        decision, decision_trace = self._run_decision(case_without_decision)
        final_payload = case_without_decision.model_dump(mode="python")
        final_payload["decision"] = decision
        final_payload["processing_trace"] = [
            *case_without_decision.processing_trace,
            decision_trace,
        ]

        return UnderwritingCase.model_validate(final_payload)

    def _run_ocr(
        self,
        materials: list[MaterialInput],
    ) -> tuple[list[OcrField], ProcessingTrace]:
        started_at = datetime.now(UTC)
        started_ns = perf_counter_ns()
        fields: list[OcrField] = []
        failures = 0

        for material_input in materials:
            try:
                fields.extend(self.ocr_provider.extract(material_input))
            except ProviderError:
                failures += 1

        finished_at = datetime.now(UTC)
        status = processing_status(len(materials), failures)

        return fields, ProcessingTrace(
            step=ProcessingStep.OCR,
            provider=self.ocr_provider.name,
            model=self.ocr_provider.model_name,
            started_at=started_at,
            finished_at=finished_at,
            latency_ms=(perf_counter_ns() - started_ns) // 1_000_000,
            status=status,
            error_code=None if failures == 0 else "OCR_PROVIDER_FAILURE",
            error_message=(
                None
                if failures == 0
                else f"{failures} of {len(materials)} material calls failed"
            ),
        )

    def _run_vision(
        self,
        materials: list[MaterialInput],
    ) -> tuple[list[RiskFinding], ProcessingTrace]:
        started_at = datetime.now(UTC)
        started_ns = perf_counter_ns()
        findings: list[RiskFinding] = []
        failures = 0

        for material_input in materials:
            try:
                findings.extend(self.vision_provider.analyze(material_input))
            except ProviderError:
                failures += 1

        finished_at = datetime.now(UTC)
        status = processing_status(len(materials), failures)

        return findings, ProcessingTrace(
            step=ProcessingStep.VISION,
            provider=self.vision_provider.name,
            model=self.vision_provider.model_name,
            started_at=started_at,
            finished_at=finished_at,
            latency_ms=(perf_counter_ns() - started_ns) // 1_000_000,
            status=status,
            error_code=None if failures == 0 else "VISION_PROVIDER_FAILURE",
            error_message=(
                None
                if failures == 0
                else f"{failures} of {len(materials)} material calls failed"
            ),
        )

    def _run_component_lookup(
        self,
        project: ProjectInfo,
    ) -> tuple[ComponentProfile | None, ProcessingTrace]:
        if self.component_provider is None:
            raise RuntimeError("component provider is not configured")

        started_at = datetime.now(UTC)
        started_ns = perf_counter_ns()
        component_profile: ComponentProfile | None = None
        status_value = ProcessingStatus.SUCCESS
        error_code: str | None = None
        error_message: str | None = None

        try:
            component_model = project.component_model
            if component_model is not None and component_model.strip():
                component_profile = self.component_provider.lookup(component_model)
        except ProviderError:
            status_value = ProcessingStatus.FAILED
            error_code = "COMPONENT_PROVIDER_FAILURE"
            error_message = "component provider lookup failed"

        return component_profile, ProcessingTrace(
            step=ProcessingStep.COMPONENT_LOOKUP,
            provider=self.component_provider.name,
            model=None,
            started_at=started_at,
            finished_at=datetime.now(UTC),
            latency_ms=(perf_counter_ns() - started_ns) // 1_000_000,
            status=status_value,
            error_code=error_code,
            error_message=error_message,
        )

    def _run_weather_lookup(
        self,
        project: ProjectInfo,
    ) -> tuple[WeatherProfile | None, ProcessingTrace]:
        if self.weather_provider is None:
            raise RuntimeError("weather provider is not configured")
        if project.longitude is None or project.latitude is None:
            raise RuntimeError("project coordinates are not configured")

        started_at = datetime.now(UTC)
        started_ns = perf_counter_ns()
        weather_profile: WeatherProfile | None = None
        status_value = ProcessingStatus.SUCCESS
        error_code: str | None = None
        error_message: str | None = None

        try:
            weather_profile = self.weather_provider.lookup(
                longitude=project.longitude,
                latitude=project.latitude,
            )
        except ProviderError:
            status_value = ProcessingStatus.FAILED
            error_code = "WEATHER_PROVIDER_FAILURE"
            error_message = "weather provider lookup failed"

        return weather_profile, ProcessingTrace(
            step=ProcessingStep.WEATHER_LOOKUP,
            provider=self.weather_provider.name,
            model=None,
            started_at=started_at,
            finished_at=datetime.now(UTC),
            latency_ms=(perf_counter_ns() - started_ns) // 1_000_000,
            status=status_value,
            error_code=error_code,
            error_message=error_message,
        )

    def _run_catastrophe_assessment(
        self,
        component_profile: ComponentProfile | None,
        weather_profile: WeatherProfile | None,
    ) -> tuple[CatastropheAssessment, ProcessingTrace]:
        if self.catastrophe_engine is None:
            raise RuntimeError("catastrophe assessment engine is not configured")

        started_at = datetime.now(UTC)
        started_ns = perf_counter_ns()
        assessment = self.catastrophe_engine.assess(
            component=component_profile,
            weather=weather_profile,
        )

        return assessment, ProcessingTrace(
            step=ProcessingStep.CATASTROPHE_ASSESSMENT,
            provider="builtin-catastrophe-assessment",
            model=None,
            started_at=started_at,
            finished_at=datetime.now(UTC),
            latency_ms=(perf_counter_ns() - started_ns) // 1_000_000,
            status=ProcessingStatus.SUCCESS,
            error_code=None,
            error_message=None,
        )

    def _run_rules(
        self,
        materials: list[Material],
    ) -> tuple[list[MaterialReview], ProcessingTrace]:
        started_at = datetime.now(UTC)
        started_ns = perf_counter_ns()
        reviews = self.rule_engine.evaluate_materials(materials)

        return reviews, ProcessingTrace(
            step=ProcessingStep.RULE_ENGINE,
            provider="builtin-rule-engine",
            model=None,
            started_at=started_at,
            finished_at=datetime.now(UTC),
            latency_ms=(perf_counter_ns() - started_ns) // 1_000_000,
            status=ProcessingStatus.SUCCESS,
            error_code=None,
            error_message=None,
        )

    def _run_decision(
        self,
        case: UnderwritingCase,
    ) -> tuple[UnderwritingDecision, ProcessingTrace]:
        started_at = datetime.now(UTC)
        started_ns = perf_counter_ns()
        decision = self.decision_engine.decide(case)

        return decision, ProcessingTrace(
            step=ProcessingStep.DECISION,
            provider="conservative-decision-engine",
            model=None,
            started_at=started_at,
            finished_at=datetime.now(UTC),
            latency_ms=(perf_counter_ns() - started_ns) // 1_000_000,
            status=ProcessingStatus.SUCCESS,
            error_code=None,
            error_message=None,
        )
