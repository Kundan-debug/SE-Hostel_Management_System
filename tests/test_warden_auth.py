from decimal import Decimal
import pytest
from werkzeug.security import generate_password_hash
from app import db
from app.models import Warden

@pytest.fixture
def warden(app):
    item = Warden(full_name="Test Warden", email="warden@example.com",
                  password_hash=generate_password_hash("WardenPass123!"))
    db.session.add(item)
    db.session.commit()
    return item

def test_warden_login_redirects_to_dashboard(client, warden):
    r=client.post("/login",data={"email":warden.email,"password":"WardenPass123!"})
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/warden/")

def test_warden_session_persists_across_requests(client, warden):
    client.post("/login",data={"email":warden.email,"password":"WardenPass123!"})
    r=client.get("/warden/")
    assert r.status_code == 200
    assert b"Warden Dashboard" in r.data

def test_student_cannot_access_warden_dashboard(logged_in_client):
    assert logged_in_client.get("/warden/").status_code == 403

def test_unauthenticated_user_cannot_access_warden_dashboard(client):
    r=client.get("/warden/")
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]

def test_warden_wrong_password_rejected(client, warden):
    r=client.post("/login",data={"email":warden.email,"password":"wrong-password"})
    assert r.status_code == 401

def test_warden_table_is_registered_in_metadata(app):
    assert "wardens" in db.metadata.tables
    assert db.metadata.tables["wardens"] is Warden.__table__


def test_warden_can_view_all_fee_records(client, app, warden):
    from datetime import date
    from decimal import Decimal
    from app.models import Fee, Student

    with app.app_context():
        student = Student.query.filter_by(email="student@gmail.com").one()
        db.session.add(Fee(
            student_id=student.id,
            description="Hostel Fee",
            fee_type="Hostel",
            amount=Decimal("5000.00"),
            due_date=date(2026, 11, 1),
        ))
        db.session.commit()

    client.post("/login", data={
        "email": warden.email,
        "password": "WardenPass123!",
    })
    response = client.get("/warden/fees")
    assert response.status_code == 200
    assert b"Hostel Fee" in response.data
    assert b"Test Student" in response.data


def test_warden_can_create_fee_record(client, app, warden):
    from app.models import Fee, Student

    with app.app_context():
        student = Student.query.filter_by(email="student@gmail.com").one()
        student_id = student.id

    client.post("/login", data={
        "email": warden.email,
        "password": "WardenPass123!",
    })
    response = client.post("/warden/fees", data={
        "student_id": student_id,
        "description": "Library Fee",
        "fee_type": "Library",
        "amount": "500.00",
        "due_date": "2026-11-15",
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Library Fee" in response.data

    with app.app_context():
        fee = Fee.query.filter_by(description="Library Fee").one()
        assert fee.status == "Due"
        assert fee.amount == Decimal("500.00")


def test_student_cannot_access_warden_fee_records(logged_in_client):
    response = logged_in_client.get("/warden/fees")
    assert response.status_code == 403


def test_unauthenticated_user_cannot_access_warden_fee_records(client):
    response = client.get("/warden/fees")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_warden_rejects_invalid_fee_amount(client, app, warden):
    from app.models import Fee

    client.post("/login", data={
        "email": warden.email,
        "password": "WardenPass123!",
    })

    response = client.post("/warden/fees", data={
        "student_id": "1",
        "description": "Invalid Fee",
        "fee_type": "Hostel",
        "amount": "-100",
        "due_date": "2026-11-15",
    }, follow_redirects=True)

    assert response.status_code == 200
    with app.app_context():
        assert Fee.query.filter_by(description="Invalid Fee").first() is None


def test_warden_rejects_nonexistent_student(client, app, warden):
    from app.models import Fee

    client.post("/login", data={
        "email": warden.email,
        "password": "WardenPass123!",
    })

    response = client.post("/warden/fees", data={
        "student_id": "99999",
        "description": "Invalid Student Fee",
        "fee_type": "Hostel",
        "amount": "500",
        "due_date": "2026-11-15",
    }, follow_redirects=True)

    assert response.status_code == 200
    with app.app_context():
        assert Fee.query.filter_by(description="Invalid Student Fee").first() is None


def test_warden_cannot_view_receipt_for_missing_payment(client, warden):
    client.post("/login", data={
        "email": warden.email,
        "password": "WardenPass123!",
    })

    response = client.get("/warden/fees/receipts/99999")
    assert response.status_code == 404


def test_warden_cannot_view_receipt_for_unsuccessful_payment(client, app, warden):
    from datetime import date
    from decimal import Decimal
    from app.models import Fee, Payment, Student

    with app.app_context():
        student = Student.query.filter_by(email="student@gmail.com").one()
        fee = Fee(
            student_id=student.id,
            description="Receipt Test Fee",
            fee_type="Hostel",
            amount=Decimal("500.00"),
            due_date=date(2026, 11, 15),
        )
        db.session.add(fee)
        db.session.flush()

        payment = Payment(
            fee_id=fee.id,
            student_id=student.id,
            amount=Decimal("500.00"),
            transaction_reference="TEST-RECEIPT-001",
            status="Pending",
        )
        db.session.add(payment)
        db.session.commit()
        payment_id = payment.id

    client.post("/login", data={
        "email": warden.email,
        "password": "WardenPass123!",
    })

    response = client.get(f"/warden/fees/receipts/{payment_id}")
    assert response.status_code == 404
