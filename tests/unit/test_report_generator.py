from app.contracts import (
    DetectionStatus,
    EquipmentInventoryItem,
    OcrField,
    OcrValueStatus,
    RiskCategory,
    UnderwritingCase,
)
from app.reports import generate_markdown_report


def make_case(*, include_decision: bool = True) -> UnderwritingCase:
    decision = None

    if include_decision:
        decision = {
            "decision": "manual_review",
            "decisive_rule_ids": ["RULE-001"],
            "reasons": ["业务核保规则尚未全部确认"],
            "conditions": [],
            "warnings": ["图片风险点需要人工复核"],
            "missing_requirements": ["补充屋顶连接照片"],
            "generated_at": "2026-09-25T10:00:00+08:00",
        }

    return UnderwritingCase.model_validate(
        {
            "schema_version": "0.1.0",
            "case_id": "case-report-001",
            "project": {
                "project_name": "示例光伏项目",
                "insured_name": "示例制造企业有限公司",
                "project_entity": "示例新能源有限公司",
                "project_type": "rooftop",
                "installation_type": "color_steel_roof",
                "site_address": "广东省示例市示例区",
                "province": "广东省",
                "city": "示例市",
                "district": "示例区",
                "longitude": 113.25,
                "latitude": 23.12,
                "proposed_start_date": "2026-10-01",
                "component_model": "PV-MODULE-580W",
                "submission_ip": None,
            },
            "materials": [
                {
                    "material_id": "material-panorama-001",
                    "category": "panorama",
                    "file_name": "site|panorama.jpg",
                    "media_type": "image/jpeg",
                    "sha256": None,
                    "captured_at": None,
                    "longitude": None,
                    "latitude": None,
                    "quality_status": "usable",
                    "quality_confidence": 0.95,
                    "quality_issues": [],
                    "parse_status": "success",
                }
            ],
            "ocr_fields": [],
            "findings": [
                {
                    "finding_id": "finding-001",
                    "material_id": "material-panorama-001",
                    "category": "severe_shading",
                    "label": "严重遮挡",
                    "detection_status": "uncertain",
                    "severity": "high",
                    "confidence": 0.72,
                    "bbox": None,
                    "evidence_text": "组件附近存在疑似大面积阴影",
                    "provider": "mock-vision",
                    "model": "mock-v1",
                    "requires_manual_review": True,
                }
            ],
            "component_profile": None,
            "weather_profile": None,
            "catastrophe_assessment": None,
            "material_reviews": [
                {
                    "material_id": "material-panorama-001",
                    "action": "warning",
                    "triggered_rule_ids": ["RULE-001"],
                    "finding_ids": ["finding-001"],
                    "ocr_field_ids": [],
                    "reasons": ["发现需要复核的图片风险"],
                    "missing_requirements": [],
                    "requires_manual_review": True,
                }
            ],
            "decision": decision,
            "processing_trace": [
                {
                    "step": "vision",
                    "provider": "mock-vision",
                    "model": "mock-v1",
                    "started_at": "2026-09-25T09:59:59+08:00",
                    "finished_at": "2026-09-25T10:00:00+08:00",
                    "latency_ms": 1000,
                    "status": "success",
                    "error_code": None,
                    "error_message": None,
                }
            ],
        }
    )


def test_generates_readable_markdown_report() -> None:
    report = generate_markdown_report(make_case())

    assert report.startswith("# 分布式光伏财产险 AI 核保报告")
    assert "**转人工复核**" in report
    assert "补充屋顶连接照片" in report
    assert "严重遮挡" in report
    assert "0.72" in report
    assert "site\\|panorama.jpg" in report
    assert "图片风险识别" in report


def test_report_explains_the_end_to_end_decision_path_and_linked_evidence() -> None:
    report = generate_markdown_report(make_case())

    assert "判断过程与追溯" in report
    assert "整单汇总顺序" in report
    assert "模型不直接生成整单结论" in report
    assert "finding-001" in report
    assert "关联视觉证据" in report
    assert "规则说明待补充" in report


def test_report_includes_extracted_ocr_fields() -> None:
    case = make_case()
    field = OcrField(
        field_id="material-panorama-001:project_name",
        material_id="material-panorama-001",
        field_name="project_name",
        raw_value="示例光伏项目",
        normalized_value="示例光伏项目",
        value_status=OcrValueStatus.EXTRACTED,
        confidence=0.98,
        provider="mock-ocr",
        model="mock-v1",
    )
    report = generate_markdown_report(
        case.model_copy(update={"ocr_fields": [field]})
    )

    assert "OCR 字段提取结果" in report
    assert "示例光伏项目" in report
    assert "0.98" in report


def test_report_includes_structured_equipment_inventory() -> None:
    case = make_case().model_copy(
        update={
            "equipment_inventory": [
                EquipmentInventoryItem(
                    source_material_id="material-panorama-001",
                    worksheet_name="设备清单",
                    row_number=2,
                    item_category="组件",
                    item_name="光伏板",
                    manufacturer="晶澳",
                    specification="JAM72D42-630W",
                    quantity="8525",
                    normalized_component_model="JAM72D42-630W",
                    rated_power_w=630,
                )
            ]
        }
    )

    report = generate_markdown_report(case)

    assert "设备清单结构化结果" in report
    assert "JAM72D42-630W" in report
    assert "630 W" in report
    assert "8525" in report



def test_renders_catastrophe_assessment_trace_label() -> None:
    case = make_case()
    trace_payload = case.processing_trace[0].model_dump(mode="python")
    trace_payload["step"] = "catastrophe_assessment"
    trace = type(case.processing_trace[0]).model_validate(trace_payload)
    report = generate_markdown_report(
        case.model_copy(update={"processing_trace": [trace]})
    )

    assert "灾害风险评估" in report


def test_report_hides_findings_outside_the_reviewed_material_scope() -> None:
    case = make_case()
    irrelevant = case.findings[0].model_copy(
        update={
            "finding_id": "finding-out-of-scope",
            "category": RiskCategory.FLAMMABLE_MATERIAL,
            "label": "out-of-scope combustible material",
            "detection_status": DetectionStatus.DETECTED,
            "evidence_text": "This finding is outside the material review scope.",
        }
    )

    report = generate_markdown_report(
        case.model_copy(update={"findings": [*case.findings, irrelevant]})
    )

    assert "outside the material review scope" not in report
    assert "0.72" in report


def test_handles_case_without_decision_or_results() -> None:
    case = make_case(include_decision=False).model_copy(
        update={
            "findings": [],
            "material_reviews": [],
            "processing_trace": [],
        }
    )

    report = generate_markdown_report(case)

    assert "建议结论：尚未生成" in report
    assert "等待规则判断或人工复核" in report
    assert report.count("| 无 |") >= 3
