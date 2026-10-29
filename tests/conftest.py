import sys
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app, db  # noqa: E402
from app.models import Student  # noqa: E402


def make_student(email, srn, hostel="Test Hostel", room="101"):
    return Student(
        full_name="Test Student",
        email=email,
        password_hash=generate_password_hash("TestPass123!"),
        contact_number="9876543210",
        srn=srn,
        parent_name="Test Parent",
        parent_contact_number="9876543211",
        hostel_name=hostel,
        room_number=room,
        id_proof_filename="test-proof.pdf",
    )


# Shared fixtures for the newer test modules. tests/test_app.py defines its
# own fixtures with the same names, which take precedence inside that module.
@pytest.fixture
def app(tmp_path):
    app = create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test-secret-key",
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
    })
    # create_app() sets UPLOAD_FOLDER itself, so override it afterwards to
    # keep test uploads out of app/static/uploads.
    app.config["UPLOAD_FOLDER"] = str(tmp_path)

    with app.app_context():
        db.create_all()
        db.session.add(make_student("student@gmail.com", "TEST123"))
        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def log_in(client, email="student@gmail.com"):
    return client.post(
        "/login",
        data={"email": email, "password": "TestPass123!"},
    )


@pytest.fixture
def logged_in_client(client):
    log_in(client)
    return client
