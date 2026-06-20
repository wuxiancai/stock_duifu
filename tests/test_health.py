from fastapi.testclient import TestClient

from backend.app.main import create_app


def test_health_endpoint_reports_service_and_postgres_config() -> None:
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "A股短线量化辅助决策系统"
    assert payload["database"] == {
        "engine": "postgresql",
        "configured": True,
    }

