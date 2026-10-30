from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

from app import db
from app.models import Warden


@pytest.fixture
def warden(app):
    item = Warden(
        full_name="Test Warden",
        email="warden@example.com",
        password_hash=generate_password_hash("WardenPass123!"),
    )
    db.session.add(item)
    db.session.commit()
    return item


def test_warden_login_redirects_to_dashboard(client, warden):
    response = client.post(
        "/login",
        data={"email": warden.email, "password": "WardenPass123!"},
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/warden/")


def test_warden_session_persists_across_requests(client, warden):
    client.post(
        "/login",
        data={"email": warden.email, "password": "WardenPass123!"},
    )
    response = client.get("/warden/")
    assert response.status_code == 200
    assert b"Warden Dashboard" in response.data


def test_student_cannot_access_warden_dashboard(logged_in_client):
    assert logged_in_client.get("/warden/").status_code == 403


def test_unauthenticated_user_cannot_access_warden_dashboard(client):
    response = client.get("/warden/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_warden_wrong_password_rejected(client, warden):
    response = client.post(
        "/login",
        data={"email": warden.email, "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_warden_table_is_registered_in_metadata(app):
    assert "wardens" in db.metadata.tables
    assert db.metadata.tables["wardens"] is Warden.__table__


def test_warden_can_view_all_fee_records(client, app, warden):
    from datetime import date
    from app.models import Fee, Student

    with app.app_context():
        student = Student.query.filter_by(email="student@gmail.com").one()
        db.session.add(
            Fee(
                student_id=student.id,
                description="Hostel Fee",
                fee_type="Hostel",
                amount=Decimal("5000.00"),
                due_date=date(2026, 11, 1),
            )
        )
        db.session.commit()

    client.post(
        "/login",
        data={"email": warden.email, "password": "WardenPass123!"},
    )
    response = client.get("/warden/fees")
    assert response.status_code == 200
    assert b"Hostel Fee" in response.data
    assert b"Test Student" in response.data


def test_warden_can_create_fee_record(client, app, warden):
    from app.models import Fee, Student

    with app.app_context():
        student = Student.query.filter_by(email="student@gmail.com").one()
        student_id = student.id

    client.post(
        "/login",
        data={"email": warden.email, "password": "WardenPass123!"},
    )
    response = client.post(
        "/warden/fees",
        data={
            "student_id": student_id,
            "description": "Library Fee",
            "fee_type": "Library",
            "amount": "500.00",
            "due_date": "2026-11-15",
        },
        follow_redirects=True,
    )

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

    client.post(
        "/login",
        data={"email": warden.email, "password": "WardenPass123!"},
    )
    response = client.post(
        "/warden/fees",
        data={
            "student_id": "1",
            "description": "Invalid Fee",
            "fee_type": "Hostel",
            "amount": "-100",
            "due_date": "2026-11-15",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    with app.app_context():
        assert Fee.query.filter_by(description="Invalid Fee").first() is None


def test_warden_rejects_nonexistent_student(client, app, warden):
    from app.models import Fee

    client.post(
        "/login",
        data={"email": warden.email, "password": "WardenPass123!"},
    )
    response = client.post(
        "/warden/fees",
        data={
            "student_id": "99999",
            "description": "Invalid Student Fee",
            "fee_type": "Hostel",
            "amount": "500",
            "due_date": "2026-11-15",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    with app.app_context():
        assert (
            Fee.query.filter_by(description="Invalid Student Fee").first()
            is None
        )


def test_warden_cannot_view_receipt_for_missing_payment(client, warden):
    client.post(
        "/login",
        data={"email": warden.email, "password": "WardenPass123!"},
    )
    response = client.get("/warden/fees/receipts/99999")
    assert response.status_code == 404


def test_warden_cannot_view_receipt_for_unsuccessful_payment(
    client, app, warden
):
    from datetime import date
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

    client.post(
        "/login",
        data={"email": warden.email, "password": "WardenPass123!"},
    )
    response = client.get(f"/warden/fees/receipts/{payment_id}")
    assert response.status_code == 404


def _create_leave_application(app):
    from datetime import date
    from app.models import LeaveApplication, Student

    with app.app_context():
        student = Student.query.filter_by(email="student@gmail.com").one()
        application = LeaveApplication(
            student_id=student.id,
            leave_type="Personal",
            start_date=date(2026, 11, 5),
            end_date=date(2026, 11, 6),
            reason="Family function",
            status="Pending",
        )
        db.session.add(application)
        db.session.commit()
        return application.id


def _login_warden(client, warden):
    return client.post(
        "/login",
        data={"email": warden.email, "password": "WardenPass123!"},
    )


def test_warden_can_view_leave_requests(client, app, warden):
    _create_leave_application(app)
    _login_warden(client, warden)

    response = client.get("/warden/leave-requests")
    assert response.status_code == 200
    assert b"Family function" in response.data
    assert b"Pending" in response.data


@pytest.mark.parametrize("decision", ["Approved", "Rejected"])
def test_warden_can_decide_pending_leave_request(
    client, app, warden, decision
):
    from app.models import LeaveApplication

    application_id = _create_leave_application(app)
    _login_warden(client, warden)

    response = client.post(
        "/warden/leave-requests",
        data={
            "application_id": str(application_id),
            "status": decision,
        },
    )
    assert response.status_code == 302

    with app.app_context():
        application = db.session.get(LeaveApplication, application_id)
        assert application.status == decision


def test_warden_rejects_invalid_leave_decision(client, app, warden):
    from app.models import LeaveApplication

    application_id = _create_leave_application(app)
    _login_warden(client, warden)

    response = client.post(
        "/warden/leave-requests",
        data={"application_id": str(application_id), "status": "Maybe"},
    )
    assert response.status_code == 302

    with app.app_context():
        application = db.session.get(LeaveApplication, application_id)
        assert application.status == "Pending"


def test_warden_cannot_change_decided_leave_request(client, app, warden):
    from app.models import LeaveApplication

    application_id = _create_leave_application(app)
    with app.app_context():
        application = db.session.get(LeaveApplication, application_id)
        application.status = "Approved"
        db.session.commit()

    _login_warden(client, warden)
    response = client.post(
        "/warden/leave-requests",
        data={"application_id": str(application_id), "status": "Rejected"},
    )
    assert response.status_code == 302

    with app.app_context():
        application = db.session.get(LeaveApplication, application_id)
        assert application.status == "Approved"


def test_student_cannot_access_warden_leave_requests(logged_in_client):
    response = logged_in_client.get("/warden/leave-requests")
    assert response.status_code == 403


def test_unauthenticated_user_cannot_access_warden_leave_requests(client):
    response = client.get("/warden/leave-requests")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_leave_decision_commit_failure_rolls_back(
    client, app, warden, monkeypatch
):
    from unittest.mock import Mock
    from sqlalchemy.exc import SQLAlchemyError

    application_id = _create_leave_application(app)
    _login_warden(client, warden)

    rollback = Mock()
    with app.app_context():
        monkeypatch.setattr(
            db.session,
            "commit",
            Mock(side_effect=SQLAlchemyError("simulated database failure")),
        )
        monkeypatch.setattr(db.session, "rollback", rollback)

        response = client.post(
            "/warden/leave-requests",
            data={
                "application_id": str(application_id),
                "status": "Approved",
            },
        )

        assert response.status_code == 302
        rollback.assert_called_once()
        assert b"Could not update the leave request" in client.get(
            "/warden/leave-requests", follow_redirects=True
        ).data


def test_warden_leave_decision_requires_csrf_token(client, app, warden):
    _login_warden(client, warden)
    app.config["WTF_CSRF_ENABLED"] = True

    response = client.post(
        "/warden/leave-requests",
        data={"request_id": "1", "decision": "approve"},
    )
    assert response.status_code == 400


def test_unauthenticated_user_cannot_access_warden_complaints(client):
    response = client.get("/warden/complaints")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_student_cannot_access_warden_complaints(logged_in_client):
    response = logged_in_client.get("/warden/complaints")
    assert response.status_code == 403


def test_warden_can_view_complaints(client, app, warden):
    from app.models import Complaint, Student

    with app.app_context():
        student = Student.query.filter_by(email="student@gmail.com").one()
        db.session.add(
            Complaint(
                student_id=student.id,
                category="Room Maintenance",
                description="Fan is not working",
                priority="High",
                status="Open",
            )
        )
        db.session.commit()

    _login_warden(client, warden)
    response = client.get("/warden/complaints")

    assert response.status_code == 200
    assert b"Fan is not working" in response.data
    assert b"Test Student" in response.data


def test_warden_can_update_complaint(client, app, warden):
    from app.models import Complaint, Student

    with app.app_context():
        student = Student.query.filter_by(email="student@gmail.com").one()
        complaint = Complaint(
            student_id=student.id,
            category="Room Maintenance",
            description="Fan is not working",
            priority="Medium",
            status="Open",
        )
        db.session.add(complaint)
        db.session.commit()
        complaint_id = complaint.id

    _login_warden(client, warden)
    response = client.post(
        "/warden/complaints",
        data={
            "complaint_id": str(complaint_id),
            "status": "Resolved",
            "priority": "High",
        },
    )

    assert response.status_code == 302
    with app.app_context():
        complaint = db.session.get(Complaint, complaint_id)
        assert complaint.status == "Resolved"
        assert complaint.priority == "High"


def test_warden_rejects_invalid_complaint_status(client, app, warden):
    from app.models import Complaint, Student

    with app.app_context():
        student = Student.query.filter_by(email="student@gmail.com").one()
        complaint = Complaint(
            student_id=student.id,
            category="Room Maintenance",
            description="Broken fan",
            priority="Medium",
            status="Open",
        )
        db.session.add(complaint)
        db.session.commit()
        complaint_id = complaint.id

    _login_warden(client, warden)
    response = client.post(
        "/warden/complaints",
        data={
            "complaint_id": str(complaint_id),
            "status": "Invalid Status",
            "priority": "High",
        },
    )
    assert response.status_code == 400