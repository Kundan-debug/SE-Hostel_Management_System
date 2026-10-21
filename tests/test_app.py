
import pytest
from datetime import date, timedelta
from decimal import Decimal

from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models import (
    Student,
    Fee,
    Payment,
    LaundryRequest,
    LeaveApplication,
)


@pytest.fixture
def app():
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret-key",
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
    })

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


@pytest.fixture
def logged_in_client(client):
    client.post(
        "/login",
        data={
            "email": "student@gmail.com",
            "password": "TestPass123!",
        },
    )
    return client


# Home and authentication tests

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


def test_logout_after_login(logged_in_client):
    response = logged_in_client.post("/logout")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


# Fees and payments tests

def test_fees_page_requires_login(client):
    response = client.get("/fees")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_student_can_view_own_fees(client, app):
    with app.app_context():
        student = Student.query.filter_by(
            email="student@gmail.com"
        ).one()

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
        data={
            "email": "student@gmail.com",
            "password": "TestPass123!",
        },
    )

    response = client.get("/fees")

    assert response.status_code == 200
    assert b"Hostel Fee" in response.data
    assert b"Outstanding balance" in response.data


def test_simulated_payment_creates_history_and_receipt(client, app):
    with app.app_context():
        student = Student.query.filter_by(
            email="student@gmail.com"
        ).one()

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
        data={
            "email": "student@gmail.com",
            "password": "TestPass123!",
        },
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
        data={
            "email": "student@gmail.com",
            "password": "TestPass123!",
        },
    )

    response = client.post(f"/fees/{fee_id}/pay")

    assert response.status_code == 404

    with app.app_context():
        fee = db.session.get(Fee, fee_id)
        assert fee.status == "Due"
        assert Payment.query.filter_by(fee_id=fee_id).count() == 0


# Laundry API tests

def valid_laundry_request():
    return {
        "item_details": "2 shirts, 1 bedsheet",
        "quantity": 3,
        "pickup_date": "2026-10-22",
    }


def test_laundry_requires_login(client):
    response = client.get("/api/laundry")
    assert response.status_code == 302


def test_create_laundry_request(logged_in_client):
    response = logged_in_client.post(
        "/api/laundry",
        json=valid_laundry_request(),
    )

    assert response.status_code == 201
    assert response.get_json()["student_id"] == "1"
    assert response.get_json()["status"] == "pending"


def test_reject_invalid_laundry_quantity(logged_in_client):
    payload = valid_laundry_request()
    payload["quantity"] = 0

    response = logged_in_client.post("/api/laundry", json=payload)
    assert response.status_code == 400


def test_student_cannot_choose_another_student_id(logged_in_client):
    payload = valid_laundry_request()
    payload["student_id"] = "999"

    response = logged_in_client.post("/api/laundry", json=payload)

    assert response.status_code == 201
    assert response.get_json()["student_id"] == "1"


def test_student_cannot_set_charges_or_payment(logged_in_client):
    payload = valid_laundry_request()
    payload["charges"] = 150.00

    response = logged_in_client.post("/api/laundry", json=payload)
    assert response.status_code == 400


def test_list_laundry_history(logged_in_client):
    logged_in_client.post(
        "/api/laundry",
        json=valid_laundry_request(),
    )

    response = logged_in_client.get("/api/laundry?student_id=999")

    assert response.status_code == 200
    items = response.get_json()
    assert len(items) == 1
    assert items[0]["student_id"] == "1"


def test_student_cannot_change_laundry_status_or_payment(
    logged_in_client,
):
    created = logged_in_client.post(
        "/api/laundry",
        json=valid_laundry_request(),
    )
    request_id = created.get_json()["id"]

    response = logged_in_client.patch(
        f"/api/laundry/{request_id}",
        json={"status": "ready", "payment_status": "paid"},
    )

    assert response.status_code == 403


def test_student_can_cancel_own_pending_request(logged_in_client):
    created = logged_in_client.post(
        "/api/laundry",
        json=valid_laundry_request(),
    )
    request_id = created.get_json()["id"]

    response = logged_in_client.patch(
        f"/api/laundry/{request_id}",
        json={"status": "cancelled"},
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "cancelled"


def test_laundry_request_not_found(logged_in_client):
    response = logged_in_client.get("/api/laundry/999")
    assert response.status_code == 404


# Apply for Leave tests

def valid_leave_form():
    start = date.today() + timedelta(days=2)
    end = start + timedelta(days=2)

    return {
        "leave_type": "Personal",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "reason": "Visiting family",
    }


def test_leave_page_requires_login(client):
    response = client.get("/leave/")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_leave_page_loads_for_logged_in_student(logged_in_client):
    response = logged_in_client.get("/leave/")
    assert response.status_code == 200


def test_student_can_apply_for_leave(logged_in_client, app):
    response = logged_in_client.post(
        "/leave/",
        data=valid_leave_form(),
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/leave/")

    with app.app_context():
        application = LeaveApplication.query.one()
        assert application.leave_type == "Personal"
        assert application.reason == "Visiting family"
        assert application.status == "Pending"


def test_leave_rejects_invalid_leave_type(logged_in_client, app):
    form = valid_leave_form()
    form["leave_type"] = "Invalid"

    logged_in_client.post("/leave/", data=form)

    with app.app_context():
        assert LeaveApplication.query.count() == 0


def test_leave_rejects_missing_fields(logged_in_client, app):
    form = valid_leave_form()
    form["reason"] = ""

    logged_in_client.post("/leave/", data=form)

    with app.app_context():
        assert LeaveApplication.query.count() == 0


def test_leave_rejects_invalid_date_format(logged_in_client, app):
    form = valid_leave_form()
    form["start_date"] = "not-a-date"

    logged_in_client.post("/leave/", data=form)

    with app.app_context():
        assert LeaveApplication.query.count() == 0


def test_leave_rejects_past_start_date(logged_in_client, app):
    form = valid_leave_form()
    form["start_date"] = (
        date.today() - timedelta(days=1)
    ).isoformat()

    logged_in_client.post("/leave/", data=form)

    with app.app_context():
        assert LeaveApplication.query.count() == 0


def test_leave_rejects_end_date_before_start_date(
    logged_in_client, app
):
    form = valid_leave_form()
    form["start_date"] = (
        date.today() + timedelta(days=5)
    ).isoformat()
    form["end_date"] = (
        date.today() + timedelta(days=3)
    ).isoformat()

    logged_in_client.post("/leave/", data=form)

    with app.app_context():
        assert LeaveApplication.query.count() == 0


def test_student_can_cancel_own_pending_leave(logged_in_client, app):
    logged_in_client.post("/leave/", data=valid_leave_form())

    with app.app_context():
        application = LeaveApplication.query.one()
        application_id = application.id

    response = logged_in_client.post(
        f"/leave/{application_id}/cancel"
    )

    assert response.status_code == 302

    with app.app_context():
        application = db.session.get(
            LeaveApplication, application_id
        )
        assert application.status == "Cancelled"


def test_student_cannot_cancel_another_students_leave(
    logged_in_client, app
):
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

        application = LeaveApplication(
            student_id=other_student.id,
            leave_type="Personal",
            start_date=date.today() + timedelta(days=2),
            end_date=date.today() + timedelta(days=3),
            reason="Private leave",
            status="Pending",
        )
        db.session.add(application)
        db.session.commit()
        application_id = application.id

    response = logged_in_client.post(
        f"/leave/{application_id}/cancel"
    )

    assert response.status_code == 404

    with app.app_context():
        application = db.session.get(
            LeaveApplication, application_id
        )
        assert application.status == "Pending"


def test_student_cannot_cancel_non_pending_leave(
    logged_in_client, app
):
    with app.app_context():
        student = Student.query.filter_by(
            email="student@gmail.com"
        ).one()

        application = LeaveApplication(
            student_id=student.id,
            leave_type="Personal",
            start_date=date.today() + timedelta(days=2),
            end_date=date.today() + timedelta(days=3),
            reason="Already approved",
            status="Approved",
        )
        db.session.add(application)
        db.session.commit()
        application_id = application.id

    logged_in_client.post(
        f"/leave/{application_id}/cancel"
    )

    with app.app_context():
        application = db.session.get(
            LeaveApplication, application_id
        )
        assert application.status == "Approved"
