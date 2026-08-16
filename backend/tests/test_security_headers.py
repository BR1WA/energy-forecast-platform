from fastapi.testclient import TestClient

from app.main import app


def test_api_responses_include_security_headers() -> None:
    response = TestClient(app).get("/api/v1/system/live")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"
    assert "camera=()" in response.headers["permissions-policy"]
