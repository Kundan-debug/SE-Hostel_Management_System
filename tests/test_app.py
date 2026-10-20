from app import create_app


def test_home_endpoint():
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret-key",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
        }
    )

    client = app.test_client()
    response = client.get("/")

    assert response.status_code == 200
    assert response.get_json() == {
        "message": "Hostel Management System API",
        "status": "running",
    }
