from fastapi.testclient import TestClient
from app.main import app


def test_navigation_assets_are_served_with_correct_types():
    client = TestClient(app)
    for url, mime in [("/workbench.js", "application/javascript"), ("/workbench.css", "text/css")]:
        response = client.get(url)
        assert response.status_code == 200
        assert mime in response.headers["content-type"]
    for url in ["/evaluation", "/vision-lab", "/risk-lab", "/evaluation/report-preview"]:
        page = client.get(url)
        assert page.status_code == 200
        assert '/workbench.js?v=' in page.text
        assert '/workbench.css?v=' in page.text


def test_launcher_can_identify_the_workspace_without_reading_full_page():
    response = TestClient(app).get("/evaluation")
    assert b"pv-underwriting-workbench" in response.content[:12000]
