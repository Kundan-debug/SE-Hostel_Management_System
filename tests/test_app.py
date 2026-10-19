
from app import create_app


def test_home_endpoint(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_PORT", "3306")
    monkeypatch.setenv("DB_NAME", "hostel_management")
    monkeypatch.setenv("DB_USER", "root")
    monkeypatch.setenv("DB_PASSWORD", "")

    app = create_app()
    app.config["TESTING"] = True

    client = app.test_client()
    response = client.get("/")

    assert response.status_code == 200
    assert response.get_json() == {
        "message": "Hostel Management System API",
        "status": "running",
    }