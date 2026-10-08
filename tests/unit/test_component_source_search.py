import uuid
from pathlib import Path

import httpx
import pytest
from app.api.component_dependencies import get_component_provider
from app.main import app
from app.providers.component import ComponentResearchAgent
from fastapi.testclient import TestClient


def correction_path() -> Path:
    return Path.cwd() / "data" / "reference" / f".component-corrections-test-{uuid.uuid4().hex}.json"


def test_research_agent_runs_ordered_sources_and_filters_domains() -> None:
    queries: list[str] = []
    stage_hosts = [
        "jasolar.com",
        "jasolar.com",
        "solar-stack.com",
        "solar-stack.com",
        "pvsyst.com",
    ]

    def respond(request: httpx.Request) -> httpx.Response:
        query = request.url.params["q"]
        queries.append(query)
        index = len(queries) - 1
        return httpx.Response(
            200,
            json={
                "web": {
                    "results": [
                        {
                            "title": (
                                "JAM72D42-630W official datasheet"
                                if index == 4
                                else "Official photovoltaic module Datasheet"
                            ),
                            "url": f"https://{stage_hosts[index]}/document-{index}.pdf",
                            "description": (
                                "Exact model appears in source title"
                                if index == 4
                                else "Series level source"
                            ),
                        },
                        {
                            "title": "spoofed",
                            "url": f"https://{stage_hosts[index]}.evil.test/fake.pdf",
                        },
                    ]
                }
            },
        )

    agent = ComponentResearchAgent(
        "test-key",
        trusted_domains=("pvsyst.com",),
        transport=httpx.MockTransport(respond),
    )
    stages = agent.search(
        model="JAM72D42-630W",
        manufacturer="JA Solar",
        series="JAM72D42",
    )

    assert [stage.stage for stage in stages] == [
        "identify_manufacturer_and_model",
        "manufacturer_exact",
        "manufacturer_series",
        "solar_stack_exact",
        "solar_stack_series",
        "trusted_web",
        "solar_stack_manual_navigation",
    ]
    assert len(queries) == 5
    assert 'site:jasolar.com "JAM72D42-630W"' in queries[0]
    assert 'site:jasolar.com "JAM72D42"' in queries[1]
    assert 'site:solar-stack.com/en/panel "JAM72D42-630W"' in queries[2]
    assert 'site:solar-stack.com/en/panel "JAM72D42"' in queries[3]
    assert "site:pvsyst.com" in queries[4]
    for stage in stages:
        assert all(document.verified is False for document in stage.documents)
        assert all(not document.url.endswith("fake.pdf") for document in stage.documents)
    assert stages[1].documents[0].model_match == "domain_and_query_match_only"
    assert stages[5].documents[0].model_match == "exact_model_text_present"


def test_research_agent_provides_no_key_solar_stack_path() -> None:
    stages = ComponentResearchAgent().search(
        model="JAM72D42-630W",
        manufacturer="JA Solar",
    )

    assert stages[0].stage == "identify_manufacturer_and_model"
    assert stages[1].stage == "search_api_unconfigured"
    assert stages[1].status == "skipped"


def test_research_agent_searches_general_web_without_domain_allowlist() -> None:
    queries: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        query = request.url.params["q"]
        queries.append(query)
        if len(queries) == 1:
            results = [
                {
                    "title": "Solar-Stack model page",
                    "url": "https://solar-stack.com/en/panel/example",
                    "description": "module listing",
                }
            ]
        else:
            results = [
                {
                    "title": "ABC-500W datasheet mirror",
                    "url": "https://docs.example.org/ABC-500W.pdf",
                    "description": "third-party document candidate",
                },
                {
                    "title": "Non-HTTPS result",
                    "url": "http://docs.example.org/ABC-500W.pdf",
                    "description": "must be filtered",
                },
            ]
        return httpx.Response(200, json={"web": {"results": results}})

    stages = ComponentResearchAgent(
        "test-key",
        transport=httpx.MockTransport(respond),
    ).search(model="ABC-500W")

    assert len(queries) == 2
    general_stage = next(stage for stage in stages if stage.stage == "general_web")
    assert general_stage.status == "found"
    assert general_stage.documents[0].url == "https://docs.example.org/ABC-500W.pdf"
    assert general_stage.documents[0].verified is False
    assert all(not document.url.startswith("http://") for document in general_stage.documents)
    assert "site:" not in queries[-1]


def test_research_agent_rejects_query_syntax_in_model() -> None:
    with pytest.raises(ValueError, match="invalid component model"):
        ComponentResearchAgent("test-key").search(model='MODEL" site:evil.test')


def test_sources_endpoint_keeps_manual_fallback_without_search_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PV_COMPONENT_SEARCH_API_KEY", "")
    response = TestClient(app).get(
        "/api/v1/components/sources?model=JAM72D42-630W&manufacturer=JA%20Solar"
    )

    assert response.status_code == 200
    result = response.json()
    assert result["search_api_configured"] is False
    assert result["verified"] is False
    assert "solar-stack.com/en/panel?q=JAM72D42-630W" in result["solar_stack_search_url"]
    stages = {stage["stage"]: stage for stage in result["stages"]}
    assert stages["search_api_unconfigured"]["status"] == "skipped"
    assert len(result["browser_search_links"]) == 2
    assert all(link["url"].startswith("https://") for link in result["browser_search_links"])
    candidate_stage = stages["local_catalog_variant_candidates"]
    assert candidate_stage["status"] == "candidate_review_required"
    assert candidate_stage["documents"][0]["title"] == "JAM72D42-630/LB"
    assert candidate_stage["documents"][0]["model_match"] == (
        "variant_candidate_requires_nameplate_confirmation"
    )


def test_manual_component_correction_is_persisted_as_missing_field_overlay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    path = correction_path()
    monkeypatch.setenv("PV_COMPONENT_CORRECTIONS_PATH", str(path))
    body = {
        "component_model": "JAM66D42-580/MB",
        "manufacturer": "JA Solar",
        "wind_load_pa": 2100,
        "snow_load_pa": 3000,
        "source_document_type": "Datasheet PDF",
        "source_url": "https://www.jasolar.com/test-datasheet.pdf",
        "parameter_sources": {
            "wind_load_pa": "https://www.jasolar.com/test-datasheet.pdf",
            "snow_load_pa": "https://www.jasolar.com/test-datasheet.pdf",
        },
        "source_note": "Test fixture only; exact model and test conditions checked.",
        "reviewer_name": "test-reviewer",
        "exact_model_verified": True,
    }
    try:
        response = TestClient(app).post("/api/v1/components/corrections", json=body)

        assert response.status_code == 201, response.text
        assert response.json()["status"] == "saved_for_future_cases"
        profile = get_component_provider().lookup("JAM66D42-580/MB")
        assert profile.wind_load_pa == 2100
        assert profile.snow_load_pa == 3000
        assert profile.parameter_sources["wind_load_pa"] == body["source_url"]
    finally:
        path.unlink(missing_ok=True)


def test_manual_component_correction_rejects_conflicting_existing_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = correction_path()
    monkeypatch.setenv("PV_COMPONENT_CORRECTIONS_PATH", str(path))
    try:
        response = TestClient(app).post(
            "/api/v1/components/corrections",
            json={
                "component_model": "JAM66D42-580/MB",
                "manufacturer": "JA Solar",
                "rated_power_w": 999,
                "source_document_type": "Datasheet PDF",
                "source_url": "https://www.jasolar.com/test-datasheet.pdf",
                "parameter_sources": {
                    "rated_power_w": "https://www.jasolar.com/test-datasheet.pdf",
                },
                "source_note": "Test fixture only.",
                "reviewer_name": "test-reviewer",
                "exact_model_verified": True,
            },
        )
        assert response.status_code == 409
        assert "rated_power_w" in response.json()["detail"]
    finally:
        path.unlink(missing_ok=True)
