import httpx
import pytest
from app.main import app
from app.providers.component.online import (
    ManufacturerDocument,
    ManufacturerDocumentFinder,
)
from fastapi.testclient import TestClient


def test_search_keeps_only_official_https_documents() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Subscription-Token"] == "test-key"
        assert "JAM72D42-630/LB" in request.url.params["q"]
        return httpx.Response(
            200,
            json={"web": {"results": [
                {"title": "Official", "url": "https://www.jasolar.com/file.pdf"},
                {"title": "Fake", "url": "https://jasolar.com.evil.test/file.pdf"},
                {"title": "Insecure", "url": "http://jasolar.com/file.pdf"},
            ]}},
        )

    finder = ManufacturerDocumentFinder(
        "test-key", transport=httpx.MockTransport(respond)
    )
    documents = finder.search("JAM72D42-630/LB")
    assert [item.title for item in documents] == ["Official"]


def test_search_rejects_query_syntax_in_model() -> None:
    finder = ManufacturerDocumentFinder("test-key")
    with pytest.raises(ValueError, match="invalid component model"):
        finder.search('MODEL" site:evil.test')


def test_source_endpoint_requires_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PV_COMPONENT_SEARCH_API_KEY", "")

    response = TestClient(app).get("/api/v1/components/sources?model=JAM72D42-630W")

    assert response.status_code == 503


def test_source_endpoint_marks_search_leads_unverified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PV_COMPONENT_SEARCH_API_KEY", "test-key")
    monkeypatch.setattr(
        ManufacturerDocumentFinder,
        "search",
        lambda self, model: [
            ManufacturerDocument("Official", "https://jasolar.com/spec.pdf", "Candidate")
        ],
    )

    response = TestClient(app).get("/api/v1/components/sources?model=JAM72D42-630W")

    assert response.status_code == 200
    assert response.json()["verified"] is False
    assert response.json()["documents"][0]["url"] == "https://jasolar.com/spec.pdf"
