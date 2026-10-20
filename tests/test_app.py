
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


from datetime import date
from decimal import Decimal

from app.models import Fee, Payment


def test_fees_page_requires_login(client):
    response = client.get("/fees")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_student_can_view_own_fees(client, app):
    with app.app_context():
        student = Student.query.filter_by(email="student@gmail.com").one()
        fee = Fee(
            student_id=student.id,
            description="Hostel Fee",
            fee_type="Hostel",
            amount=Decimal("5000.00"),
            due_date=date(2026, 11, 1),
        )
        db.session.add(fee)
        db.session.commit()

    client.post(
        "/login",
        data={"email": "student@gmail.com", "password": "TestPass123!"},
    )
    response = client.get("/fees")

    assert response.status_code == 200
    assert b"Hostel Fee" in response.data
    assert b"Outstanding balance" in response.data


def test_simulated_payment_creates_history_and_receipt(client, app):
    with app.app_context():
        student = Student.query.filter_by(email="student@gmail.com").one()
        fee = Fee(
            student_id=student.id,
            description="Mess Fee",
            fee_type="Mess",
            amount=Decimal("1500.00"),
            due_date=date(2026, 11, 1),
        )
        db.session.add(fee)
        db.session.commit()
        fee_id = fee.id

    client.post(
        "/login",
        data={"email": "student@gmail.com", "password": "TestPass123!"},
    )
    response = client.post(f"/fees/{fee_id}/pay")

    assert response.status_code == 302
    assert "/payments/" in response.headers["Location"]

    with app.app_context():
        fee = db.session.get(Fee, fee_id)
        payment = Payment.query.filter_by(fee_id=fee_id).one()
        assert fee.status == "Paid"
        assert payment.status == "Success"
        assert payment.amount == Decimal("1500.00")
        payment_id = payment.id

    response = client.get(f"/payments/{payment_id}/receipt")
    assert response.status_code == 200
    assert b"DEMO RECEIPT" in response.data


def test_student_cannot_pay_another_students_fee(client, app):
    with app.app_context():
        other_student = Student(
            full_name="Other Student",
            email="other@gmail.com",
            password_hash=generate_password_hash("OtherPass123!"),
            contact_number="9876543212",
            srn="OTHER123",
            parent_name="Other Parent",
            parent_contact_number="9876543213",
            hostel_name="Other Hostel",
            room_number="202",
            id_proof_filename="other.pdf",
        )
        db.session.add(other_student)
        db.session.flush()

        fee = Fee(
            student_id=other_student.id,
            description="Private Fee",
            fee_type="Hostel",
            amount=Decimal("2000.00"),
            due_date=date(2026, 11, 1),
        )
        db.session.add(fee)
        db.session.commit()
        fee_id = fee.id

    client.post(
        "/login",
        data={"email": "student@gmail.com", "password": "TestPass123!"},
    )
    response = client.post(f"/fees/{fee_id}/pay")
    assert response.status_code == 404

    with app.app_context():
        fee = db.session.get(Fee, fee_id)
        assert fee.status == "Due"
        assert Payment.query.filter_by(fee_id=fee_id).count() == 0
