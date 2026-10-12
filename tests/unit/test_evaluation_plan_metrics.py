from scripts.evaluate_cases import evaluate_cases


def test_duplicate_photos_count_once_per_case_category_and_miss_still_counts():
    truth = [{
        "case_id": "reject-1", "expected_decision": "recommend_reject",
        "required_high_risk_categories": [
            {"category": "agriculture_environment", "material_id": "front"},
            {"category": "agriculture_environment", "material_id": "overhead"},
        ],
    }]
    predicted = [{
        "case_id": "reject-1", "decision": {"decision": "request_more"},
        "findings": [{
            "category": "forest_environment", "material_id": "front",
            "detection_status": "detected",
        }],
    }]
    result = evaluate_cases(truth, predicted)
    assert result["high_risk_scenes_expected"] == 1
    assert result["risk_missed_cases"] == 1
    assert result["missed_risks_caught_by_review_or_supplement"] == 1
    assert result["wrongful_release_cases"] == 0


def test_wrongful_release_and_compliant_false_positive_are_separate():
    truth = [
        {"case_id": "reject", "expected_decision": "recommend_reject",
         "required_high_risk_categories": ["forest_environment"]},
        {"case_id": "normal", "expected_decision": "accept", "compliant": True},
    ]
    predicted = [
        {"case_id": "reject", "decision": {"decision": "conditional_accept"}, "findings": []},
        {"case_id": "normal", "decision": {"decision": "recommend_reject"},
         "findings": [{"category": "agriculture_environment", "detection_status": "detected"}]},
    ]
    result = evaluate_cases(truth, predicted)
    assert result["wrongful_release_cases"] == 1
    assert result["compliant_false_positive_cases"] == 1
    assert result["compliant_false_positive_rate"] == 1
    assert result["wrongful_rejection_cases"] == 1
    assert result["high_risk_recall"] == 0


def test_wind_recalculation_error_is_counted_separately_from_decision():
    truth = [{
        "case_id": "wind", "expected_decision": "manual_review",
        "expected_wind_comparison": {
            "status": "calculated", "r_historical_over_capacity": 1.2,
            "f_exceedance_percent": 50.0,
        },
    }]
    predicted = [{
        "case_id": "wind", "decision": {"decision": "manual_review"},
        "catastrophe_assessment": {"wind_comparison": {
            "status": "calculated", "r_historical_over_capacity": 0.8,
            "f_exceedance_percent": 50.0,
        }},
    }]
    result = evaluate_cases(truth, predicted)
    assert result["wind_recalculable_cases"] == 1
    assert result["wind_calculated_cases"] == 1
    assert result["wind_recalculation_errors"] == 1
    assert result["decision_accuracy"] == 1
    assert result["compliant_false_positive_rate"] is None


def test_severe_shading_false_positive_is_counted_for_compliant_case():
    result = evaluate_cases(
        [{"case_id": "normal", "compliant": True}],
        [{"case_id": "normal", "findings": [{
            "category": "severe_shading", "detection_status": "detected",
        }]}],
    )
    assert result["compliant_false_positive_cases"] == 1


def test_wind_ground_truth_requires_numeric_expected_values():
    import pytest

    with pytest.raises(ValueError, match="f_exceedance_percent"):
        evaluate_cases(
            [{"case_id": "wind", "expected_wind_comparison": {
                "status": "calculated", "r_historical_over_capacity": 1.2,
            }}],
            [{"case_id": "wind"}],
        )


def test_category_auto_handling_and_invalid_evidence_reference_metrics():
    truth = [{
        "case_id": "rejected", "expected_decision": "recommend_reject",
        "required_high_risk_categories": ["forest_environment", "severe_shading"],
    }, {
        "case_id": "normal", "expected_decision": "accept",
        "eligible_for_auto_decision": True, "compliant": True,
    }]
    predicted = [{
        "case_id": "rejected", "decision": {"decision": "conditional_accept"},
        "materials": [{"material_id": "roof"}],
        "findings": [{"category": "forest_environment", "material_id": "other",
                      "detection_status": "detected"}],
    }, {
        "case_id": "normal", "decision": {"decision": "accept"},
        "materials": [], "findings": [],
    }]
    result = evaluate_cases(truth, predicted)
    assert result["high_risk_by_category"]["forest_environment"]["recall"] == 1
    assert result["high_risk_by_category"]["severe_shading"]["missed"] == 1
    assert result["wrongful_release_rate"] == 1
    assert result["auto_eligible_correct_rate"] == 1
    assert result["evidence_reference_checked_cases"] == 2
    assert result["invalid_evidence_references"] == 1
