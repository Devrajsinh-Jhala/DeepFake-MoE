from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app


def test_upload_analysis_flow_returns_completed_result() -> None:
    image = Image.new("RGB", (64, 64), "white")
    output = BytesIO()
    image.save(output, format="PNG")

    with TestClient(app) as client:
        response = client.post(
            "/analyses",
            data={"consent_confirmed": "true"},
            files={"file": ("test.png", output.getvalue(), "image/png")},
        )
        assert response.status_code == 202
        analysis_id = response.json()["id"]

        result_response = client.get(f"/analyses/{analysis_id}")
        assert result_response.status_code == 200
        payload = result_response.json()
        assert payload["status"] == "completed"
        assert payload["result"]["verdict"]["label"] in {
            "inconclusive",
            "likely_real",
            "likely_manipulated_or_deepfake",
            "likely_ai_generated",
        }

        report_response = client.get(f"/analyses/{analysis_id}/report?format=pdf")
        assert report_response.status_code == 200
        assert report_response.content.startswith(b"%PDF")


def test_security_headers_are_present() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-frame-options"] == "DENY"


def test_ready_and_metrics_endpoints() -> None:
    with TestClient(app) as client:
        ready = client.get("/ready")
        metrics = client.get("/metrics")

    assert ready.status_code == 200
    assert ready.json()["checks"]["database"] == "ok"
    assert metrics.status_code == 200
    assert "aida_http_requests_total" in metrics.text


def test_analysis_can_be_deleted_early() -> None:
    image = Image.new("RGB", (64, 64), "white")
    output = BytesIO()
    image.save(output, format="PNG")

    with TestClient(app) as client:
        response = client.post(
            "/analyses",
            data={"consent_confirmed": "true"},
            files={"file": ("test.png", output.getvalue(), "image/png")},
        )
        analysis_id = response.json()["id"]

        delete_response = client.delete(f"/analyses/{analysis_id}")
        assert delete_response.status_code == 204

        get_response = client.get(f"/analyses/{analysis_id}")
        assert get_response.status_code == 404
