
import pytest
from app import create_app, db


@pytest.fixture
def client():
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
    })

    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def valid_request():
    return {
        "student_id": "STU001",
        "item_details": "2 shirts, 1 bedsheet",
        "quantity": 3,
        "pickup_date": "2026-10-22",
        "charges": 150.00,
    }


def test_create_laundry_request(client):
    response = client.post("/api/laundry", json=valid_request())
    assert response.status_code == 201
    assert response.get_json()["student_id"] == "STU001"


def test_reject_invalid_quantity(client):
    payload = valid_request()
    payload["quantity"] = 0
    response = client.post("/api/laundry", json=payload)
    assert response.status_code == 400


def test_list_laundry_history(client):
    client.post("/api/laundry", json=valid_request())
    response = client.get("/api/laundry?student_id=STU001")
    assert response.status_code == 200
    assert len(response.get_json()) == 1


def test_update_status_and_payment(client):
    created = client.post("/api/laundry", json=valid_request())
    request_id = created.get_json()["id"]

    response = client.patch(
        f"/api/laundry/{request_id}",
        json={"status": "ready", "payment_status": "paid"},
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "ready"
    assert response.get_json()["payment_status"] == "paid"


def test_request_not_found(client):
    response = client.get("/api/laundry/999")
    assert response.status_code == 404
