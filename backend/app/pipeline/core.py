from datetime import UTC, datetime
from time import perf_counter_ns

from app.contracts import (
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
)
from app.decision import DecisionEngine
from app.providers import (
    MaterialInput,
    OcrProvider,
    ProviderError,
    VisionProvider,
)
from app.rules import RuleEngine


def processing_status(total: int, failures: int) -> ProcessingStatus:
    """根据Provider调用失败数量生成处理状态。"""

    if failures == 0:
        return ProcessingStatus.SUCCESS
    if total > 0 and failures == total:
        return ProcessingStatus.FAILED
    return ProcessingStatus.PARTIAL


class UnderwritingPipeline:
    """协调Provider、规则引擎和决策引擎并组装核保案件。"""

    def __init__(
        self,
        ocr_provider: OcrProvider,
        vision_provider: VisionProvider,
        rule_engine: RuleEngine | None = None,
        decision_engine: DecisionEngine | None = None,
    ) -> None:
        self.ocr_provider = ocr_provider
        self.vision_provider = vision_provider
        self.rule_engine = RuleEngine() if rule_engine is None else rule_engine
        self.decision_engine = (
            DecisionEngine() if decision_engine is None else decision_engine
        )

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
        material_reviews, rule_trace = self._run_rules(material_models)

        case_without_decision = UnderwritingCase(
            schema_version="0.1.0",
            case_id=case_id,
            project=project,
            materials=material_models,
            ocr_fields=ocr_fields,
            findings=findings,
            component_profile=None,
            weather_profile=None,
            catastrophe_assessment=None,
            material_reviews=material_reviews,
            decision=None,
            processing_trace=[ocr_trace, vision_trace, rule_trace],
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

    def _run_rules(
        self,
        materials: list[Material],
    ) -> tuple[list[MaterialReview], ProcessingTrace]:
        started_at = datetime.now(UTC)
        started_ns = perf_counter_ns()

        reviews = self.rule_engine.evaluate_materials(materials)

        finished_at = datetime.now(UTC)

        return reviews, ProcessingTrace(
            step=ProcessingStep.RULE_ENGINE,
            provider="builtin-rule-engine",
            model=None,
            started_at=started_at,
            finished_at=finished_at,
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

        finished_at = datetime.now(UTC)

        return decision, ProcessingTrace(
            step=ProcessingStep.DECISION,
            provider="conservative-decision-engine",
            model=None,
            started_at=started_at,
            finished_at=finished_at,
            latency_ms=(perf_counter_ns() - started_ns) // 1_000_000,
            status=ProcessingStatus.SUCCESS,
            error_code=None,
            error_message=None,
        )