from app.contracts import UnderwritingCase
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
