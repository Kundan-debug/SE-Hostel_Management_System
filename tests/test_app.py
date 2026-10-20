
import pytest
from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models import Student


@pytest.fixture
def app():
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret-key",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
        }
    )

    with app.app_context():
        db.create_all()

        student = Student(
            full_name="Test Student",
            email="student@gmail.com",
            password_hash=generate_password_hash("TestPass123!"),
            contact_number="9876543210",
            srn="TEST123",
            parent_name="Test Parent",
            parent_contact_number="9876543211",
            hostel_name="Test Hostel",
            room_number="101",
            id_proof_filename="test-proof.pdf",
        )

        db.session.add(student)
        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_home_endpoint(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.get_json() == {
        "message": "Hostel Management System API",
        "status": "running",
    }


def test_login_page_loads(client):
    response = client.get("/login")

    assert response.status_code == 200
    assert b"Student Login" in response.data


def test_login_with_correct_credentials(client):
    response = client.post(
        "/login",
        data={
            "email": "student@gmail.com",
            "password": "TestPass123!",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_login_with_incorrect_password(client):
    response = client.post(
        "/login",
        data={
            "email": "student@gmail.com",
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401
    assert b"Invalid email or password." in response.data


def test_login_with_unknown_email(client):
    response = client.post(
        "/login",
        data={
            "email": "unknown@gmail.com",
            "password": "TestPass123!",
        },
    )

    assert response.status_code == 401
    assert b"Invalid email or password." in response.data


def test_logout_requires_login(client):
    response = client.post("/logout")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_logout_after_login(client):
    client.post(
        "/login",
        data={
            "email": "student@gmail.com",
            "password": "TestPass123!",
        },
    )

    response = client.post("/logout")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
