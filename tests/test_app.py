
import pytest
from io import BytesIO
from datetime import datetime
from datetime import date, timedelta, time
from decimal import Decimal

from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models import (
    Student,
    Fee,
    Payment,
    LaundryRequest,
    LeaveApplication,
    CommonFacility,
    FacilityBooking,
    Announcement,
    MessMenu,
    MealRegistration,
    MessAttendance,
    MessFeedback,
    MessHoliday,
    MessFee,
    LostFoundItem,
)


@pytest.fixture
def app():
    app = create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
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


def test_home_endpoint(logged_in_client):
    response = logged_in_client.get("/")

    assert response.status_code == 200
    assert b"Hostel Management System" in response.data
    assert b"Student Profile" in response.data
    assert b"Room Details" in response.data
    assert b"Fees and Payments" in response.data
    assert b"Leave Applications" in response.data
    assert b"Common Facilities" in response.data


def test_security_headers(logged_in_client):
    response = logged_in_client.get("/")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


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
    assert response.headers["Location"].endswith("/room-details/")


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


# Book Common Facility tests

def create_test_facility(app, capacity=2, is_available=True):
    with app.app_context():
        facility = CommonFacility(
            name="Test Gym",
            description="Gym for testing",
            location="Ground Floor",
            capacity=capacity,
            is_available=is_available,
        )
        db.session.add(facility)
        db.session.commit()
        return facility.id


def valid_facility_booking(facility_id):
    return {
        "facility_id": facility_id,
        "booking_date": (
            date.today() + timedelta(days=1)
        ).isoformat(),
        "start_time": "10:00",
        "end_time": "11:00",
    }


def test_facility_list_requires_login(client):
    response = client.get("/facilities/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_booking_history_requires_login(client):
    response = client.get("/facilities/bookings")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_create_booking_requires_login(client):
    response = client.post(
        "/facilities/bookings",
        json={
            "facility_id": 1,
            "booking_date": (
                date.today() + timedelta(days=1)
            ).isoformat(),
            "start_time": "10:00",
            "end_time": "11:00",
        },
    )
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_student_can_list_facilities(logged_in_client, app):
    facility_id = create_test_facility(app)

    response = logged_in_client.get("/facilities/")

    assert response.status_code == 200
    facilities = response.get_json()
    assert len(facilities) == 1
    assert facilities[0]["id"] == facility_id
    assert facilities[0]["name"] == "Test Gym"
    assert facilities[0]["is_available"] is True


def test_student_can_create_booking(logged_in_client, app):
    facility_id = create_test_facility(app)

    response = logged_in_client.post(
        "/facilities/bookings",
        json=valid_facility_booking(facility_id),
    )

    assert response.status_code == 201
    result = response.get_json()
    assert result["booking"]["facility_id"] == facility_id
    assert result["booking"]["facility_name"] == "Test Gym"
    assert result["booking"]["status"] == "Pending"

    with app.app_context():
        booking = FacilityBooking.query.one()
        assert booking.facility_id == facility_id
        assert booking.status == "Pending"


def test_booking_rejects_missing_fields(logged_in_client):
    response = logged_in_client.post(
        "/facilities/bookings",
        json={"facility_id": 1},
    )

    assert response.status_code == 400


def test_booking_rejects_invalid_date_or_time(logged_in_client):
    response = logged_in_client.post(
        "/facilities/bookings",
        json={
            "facility_id": 1,
            "booking_date": "not-a-date",
            "start_time": "10:00",
            "end_time": "11:00",
        },
    )

    assert response.status_code == 400


def test_booking_rejects_past_date(logged_in_client, app):
    facility_id = create_test_facility(app)
    payload = valid_facility_booking(facility_id)
    payload["booking_date"] = (
        date.today() - timedelta(days=1)
    ).isoformat()

    response = logged_in_client.post(
        "/facilities/bookings",
        json=payload,
    )

    assert response.status_code == 400


def test_booking_rejects_end_time_before_start_time(
    logged_in_client, app
):
    facility_id = create_test_facility(app)
    payload = valid_facility_booking(facility_id)
    payload["start_time"] = "11:00"
    payload["end_time"] = "10:00"

    response = logged_in_client.post(
        "/facilities/bookings",
        json=payload,
    )

    assert response.status_code == 400


def test_booking_rejects_nonexistent_facility(logged_in_client):
    response = logged_in_client.post(
        "/facilities/bookings",
        json=valid_facility_booking(9999),
    )

    assert response.status_code == 404


def test_booking_rejects_unavailable_facility(
    logged_in_client, app
):
    facility_id = create_test_facility(
        app, is_available=False
    )

    response = logged_in_client.post(
        "/facilities/bookings",
        json=valid_facility_booking(facility_id),
    )

    assert response.status_code == 409


def test_booking_rejects_fully_booked_time_slot(
    logged_in_client, app
):
    facility_id = create_test_facility(app, capacity=1)
    payload = valid_facility_booking(facility_id)

    first_response = logged_in_client.post(
        "/facilities/bookings",
        json=payload,
    )
    assert first_response.status_code == 201

    second_response = logged_in_client.post(
        "/facilities/bookings",
        json=payload,
    )
    assert second_response.status_code == 409


def test_student_can_view_own_booking_history(
    logged_in_client, app
):
    facility_id = create_test_facility(app)

    logged_in_client.post(
        "/facilities/bookings",
        json=valid_facility_booking(facility_id),
    )

    response = logged_in_client.get("/facilities/bookings")

    assert response.status_code == 200
    bookings = response.get_json()
    assert len(bookings) == 1
    assert bookings[0]["facility_name"] == "Test Gym"
    assert bookings[0]["status"] == "Pending"


def test_student_can_cancel_own_booking(
    logged_in_client, app
):
    facility_id = create_test_facility(app)

    created = logged_in_client.post(
        "/facilities/bookings",
        json=valid_facility_booking(facility_id),
    )
    booking_id = created.get_json()["booking"]["id"]

    response = logged_in_client.post(
        f"/facilities/bookings/{booking_id}/cancel"
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "Cancelled"

    with app.app_context():
        booking = db.session.get(FacilityBooking, booking_id)
        assert booking.status == "Cancelled"


def test_student_cannot_cancel_another_students_booking(
    logged_in_client, app
):
    facility_id = create_test_facility(app)

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

        booking = FacilityBooking(
            student_id=other_student.id,
            facility_id=facility_id,
            booking_date=date.today() + timedelta(days=1),
            start_time=time(10, 0),
            end_time=time(11, 0),
            status="Pending",
        )
        db.session.add(booking)
        db.session.commit()
        booking_id = booking.id

    response = logged_in_client.post(
        f"/facilities/bookings/{booking_id}/cancel"
    )

    assert response.status_code == 404

    with app.app_context():
        booking = db.session.get(FacilityBooking, booking_id)
        assert booking.status == "Pending"


def test_student_cannot_cancel_booking_twice(
    logged_in_client, app
):
    facility_id = create_test_facility(app)

    created = logged_in_client.post(
        "/facilities/bookings",
        json=valid_facility_booking(facility_id),
    )
    booking_id = created.get_json()["booking"]["id"]

    first_response = logged_in_client.post(
        f"/facilities/bookings/{booking_id}/cancel"
    )
    assert first_response.status_code == 200

    second_response = logged_in_client.post(
        f"/facilities/bookings/{booking_id}/cancel"
    )
    assert second_response.status_code == 409

def test_profile_requires_login(client):
    response = client.get("/profile/")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_student_can_view_own_profile(logged_in_client):
    response = logged_in_client.get("/profile/")

    assert response.status_code == 200
    assert b"Test Student" in response.data
    assert b"student@gmail.com" in response.data
    assert b"Test Hostel" in response.data


def test_student_can_update_own_profile(logged_in_client, app):
    response = logged_in_client.post(
        "/profile/edit",
        data={
            "full_name": "Updated Student",
            "email": "updated@gmail.com",
            "contact_number": "9123456789",
            "parent_name": "Updated Parent",
            "parent_contact_number": "9123456788",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Your profile has been updated." in response.data

    with app.app_context():
        student = Student.query.filter_by(srn="TEST123").first()
        assert student.full_name == "Updated Student"
        assert student.email == "updated@gmail.com"


def test_profile_rejects_invalid_contact_number(logged_in_client, app):
    response = logged_in_client.post(
        "/profile/edit",
        data={
            "full_name": "Test Student",
            "email": "student@gmail.com",
            "contact_number": "123",
            "parent_name": "Test Parent",
            "parent_contact_number": "9876543211",
        },
    )

    assert response.status_code == 400
    assert b"Enter exactly 10 digits." in response.data

    with app.app_context():
        student = Student.query.filter_by(srn="TEST123").first()
        assert student.contact_number == "9876543210"


def test_profile_rejects_duplicate_email(logged_in_client, app):
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
        db.session.commit()

    response = logged_in_client.post(
        "/profile/edit",
        data={
            "full_name": "Test Student",
            "email": "other@gmail.com",
            "contact_number": "9876543210",
            "parent_name": "Test Parent",
            "parent_contact_number": "9876543211",
        },
    )

    assert response.status_code == 400
    assert b"This email is already registered." in response.data


def test_profile_photo_rejects_unsupported_extension(logged_in_client):
    response = logged_in_client.post(
        "/profile/photo",
        data={
            "profile_photo": (
                BytesIO(b"not an image"),
                "photo.gif",
            )
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Upload a JPG, JPEG, or PNG image." in response.data


def test_student_can_upload_profile_photo(logged_in_client, app):
    response = logged_in_client.post(
        "/profile/photo",
        data={
            "profile_photo": (
                BytesIO(b"test image content"),
                "photo.jpg",
            )
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Profile photo updated." in response.data

    from pathlib import Path

    with app.app_context():
        upload_folder = Path(app.config["UPLOAD_FOLDER"])
        photos = list(upload_folder.glob("profile_1_*.jpg"))

        assert len(photos) == 1
        assert photos[0].read_bytes() == b"test image content"


# Notifications and announcements tests

def test_announcements_require_login(client):
    response = client.get("/announcements/")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_student_can_view_announcements(logged_in_client, app):
    with app.app_context():
        announcement = Announcement(
            title="Water Supply Maintenance",
            message="Water supply will be interrupted tomorrow.",
            category="Maintenance",
        )
        db.session.add(announcement)
        db.session.commit()

    response = logged_in_client.get("/announcements/")

    assert response.status_code == 200
    assert b"Notifications & Announcements" in response.data
    assert b"Water Supply Maintenance" in response.data
    assert b"Water supply will be interrupted tomorrow." in response.data
    assert b"Maintenance" in response.data


def test_announcements_are_ordered_newest_first(
    logged_in_client, app
):
    with app.app_context():
        older = Announcement(
            title="Older Announcement",
            message="This is an older notice.",
            category="General",
            published_at=datetime(2026, 1, 1),
        )
        newer = Announcement(
            title="Newer Announcement",
            message="This is a newer notice.",
            category="Events",
            published_at=datetime(2026, 2, 1),
        )

        db.session.add_all([older, newer])
        db.session.commit()

    response = logged_in_client.get("/announcements/")

    assert response.status_code == 200
    older_position = response.data.index(b"Older Announcement")
    newer_position = response.data.index(b"Newer Announcement")
    assert newer_position < older_position


def test_expired_announcements_are_hidden(
    logged_in_client, app
):
    with app.app_context():
        expired = Announcement(
            title="Expired Notice",
            message="This notice should no longer appear.",
            category="General",
            published_at=datetime(2026, 1, 1),
            expires_at=datetime(2026, 1, 2),
        )
        current = Announcement(
            title="Current Notice",
            message="This notice is still available.",
            category="General",
        )

        db.session.add_all([expired, current])
        db.session.commit()

    response = logged_in_client.get("/announcements/")

    assert response.status_code == 200
    assert b"Current Notice" in response.data
    assert b"Expired Notice" not in response.data


# Manage Mess tests

def test_manage_mess_requires_login(client):
    response = client.get("/mess/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_manage_mess_page_loads(logged_in_client):
    response = logged_in_client.get("/mess/")
    assert response.status_code == 200
    assert b"Weekly Menu" in response.data
    assert b"Mess Attendance" in response.data
    assert b"Feedback" in response.data
    assert b"Mess Holidays" in response.data
    assert b"Mess Fee Information" in response.data
    assert b"currently unavailable" in response.data


def test_student_can_view_weekly_menu(logged_in_client, app):
    with app.app_context():
        db.session.add(
            MessMenu(
                day_of_week="Monday",
                meal_type="Breakfast",
                menu_items="Idli, sambar and chutney",
                start_time=time(7, 30),
                end_time=time(9, 0),
            )
        )
        db.session.commit()

    response = logged_in_client.get("/mess/")
    assert response.status_code == 200
    assert b"Idli, sambar and chutney" in response.data
    assert b"Monday" in response.data


def test_student_can_register_for_meal(logged_in_client, app):
    with app.app_context():
        menu = MessMenu(
            day_of_week="Tuesday",
            meal_type="Lunch",
            menu_items="Rice and dal",
            start_time=time(12, 30),
            end_time=time(14, 0),
        )
        db.session.add(menu)
        db.session.commit()
        menu_id = menu.id

    response = logged_in_client.post(
        "/mess/register",
        data={"menu_id": str(menu_id)},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Meal registration successful" in response.data

    with app.app_context():
        registration = MealRegistration.query.filter_by(
            student_id=1,
            menu_id=menu_id,
        ).first()
        assert registration is not None


def test_student_cannot_register_for_same_meal_twice(
    logged_in_client, app
):
    with app.app_context():
        menu = MessMenu(
            day_of_week="Wednesday",
            meal_type="Dinner",
            menu_items="Chapati and curry",
            start_time=time(19, 0),
            end_time=time(20, 30),
        )
        db.session.add(menu)
        db.session.commit()
        menu_id = menu.id

    logged_in_client.post(
        "/mess/register", data={"menu_id": str(menu_id)}
    )
    response = logged_in_client.post(
        "/mess/register",
        data={"menu_id": str(menu_id)},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"already registered" in response.data

    with app.app_context():
        assert MealRegistration.query.filter_by(
            student_id=1,
            menu_id=menu_id,
        ).count() == 1


def test_student_cannot_register_for_unavailable_meal(
    logged_in_client, app
):
    with app.app_context():
        menu = MessMenu(
            day_of_week="Thursday",
            meal_type="Lunch",
            menu_items="Vegetable pulao",
            start_time=time(12, 0),
            end_time=time(13, 30),
            is_available=False,
        )
        db.session.add(menu)
        db.session.commit()
        menu_id = menu.id

    response = logged_in_client.post(
        "/mess/register",
        data={"menu_id": str(menu_id)},
        follow_redirects=True,
    )

    assert b"unavailable for registration" in response.data

    with app.app_context():
        assert MealRegistration.query.filter_by(
            student_id=1,
            menu_id=menu_id,
        ).count() == 0


def test_student_can_submit_mess_feedback(logged_in_client, app):
    response = logged_in_client.post(
        "/mess/feedback",
        data={
            "category": "Feedback",
            "message": "The food quality was good.",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Your submission has been recorded" in response.data
    assert b"The food quality was good." in response.data

    with app.app_context():
        item = MessFeedback.query.filter_by(student_id=1).first()
        assert item is not None
        assert item.category == "Feedback"


def test_mess_feedback_rejects_invalid_category(logged_in_client, app):
    response = logged_in_client.post(
        "/mess/feedback",
        data={"category": "Other", "message": "Test message"},
        follow_redirects=True,
    )

    assert b"Select Feedback or Complaint" in response.data

    with app.app_context():
        assert MessFeedback.query.count() == 0


def test_mess_feedback_rejects_empty_message(logged_in_client, app):
    response = logged_in_client.post(
        "/mess/feedback",
        data={"category": "Complaint", "message": "   "},
        follow_redirects=True,
    )

    assert b"Enter a message" in response.data

    with app.app_context():
        assert MessFeedback.query.count() == 0


def test_student_only_sees_own_mess_records(logged_in_client, app):
    with app.app_context():
        other_student = Student(
            full_name="Another Student",
            email="another@gmail.com",
            password_hash=generate_password_hash("OtherPass123!"),
            contact_number="9876543212",
            srn="OTHER123",
            parent_name="Other Parent",
            parent_contact_number="9876543213",
            hostel_name="Test Hostel",
            room_number="102",
            id_proof_filename="other-proof.pdf",
        )
        db.session.add(other_student)
        db.session.commit()

        db.session.add(
            MessFeedback(
                student_id=other_student.id,
                category="Complaint",
                message="Private complaint",
            )
        )
        db.session.commit()

    response = logged_in_client.get("/mess/")
    assert response.status_code == 200
    assert b"Private complaint" not in response.data


def test_missing_secret_key_raises_error(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(RuntimeError, match="SECRET_KEY must be set in the environment"):
        create_app()


# Lost and Found tests

def test_lost_found_requires_login(client):
    response = client.get("/lost-found/")
    assert response.status_code == 302
    assert "/login" in response.location


def test_student_can_view_lost_found(logged_in_client):
    response = logged_in_client.get("/lost-found/")
    assert response.status_code == 200
    assert b"Lost and Found" in response.data


def test_student_can_report_found_item(logged_in_client, app):
    response = logged_in_client.post(
        "/lost-found/report",
        data={
            "item_type": "Found",
            "title": "Black Wallet",
            "description": "A black wallet found near the library.",
            "location": "Library",
            "item_date": date.today().isoformat(),
        },
    )

    assert response.status_code == 302

    with app.app_context():
        item = LostFoundItem.query.filter_by(title="Black Wallet").first()
        assert item is not None
        assert item.item_type == "Found"
        assert item.status == "Open"


def test_student_can_search_lost_found_items(logged_in_client, app):
    with app.app_context():
        student = Student.query.filter_by(email="student@gmail.com").first()
        db.session.add(
            LostFoundItem(
                student_id=student.id,
                item_type="Lost",
                title="Blue Water Bottle",
                description="Blue bottle with a sticker.",
                location="Cafeteria",
                item_date=date.today(),
                status="Open",
            )
        )
        db.session.commit()

    response = logged_in_client.get("/lost-found/?q=Water")

    assert response.status_code == 200
    assert b"Blue Water Bottle" in response.data


def test_student_can_claim_found_item(logged_in_client, app):
    with app.app_context():
        student = Student.query.filter_by(email="student@gmail.com").first()
        other_student = Student(
            full_name="Other Student",
            email="other@gmail.com",
            password_hash=generate_password_hash("OtherPass123!"),
            contact_number="9876543212",
            srn="OTHER123",
            parent_name="Other Parent",
            parent_contact_number="9876543213",
            hostel_name="Test Hostel",
            room_number="102",
            id_proof_filename="other-proof.pdf",
        )
        db.session.add(other_student)
        db.session.commit()

        item = LostFoundItem(
            student_id=other_student.id,
            item_type="Found",
            title="Found Keys",
            description="Keys found near the entrance.",
            location="Entrance",
            item_date=date.today(),
            status="Open",
        )
        db.session.add(item)
        db.session.commit()
        item_id = item.id

    response = logged_in_client.post(f"/lost-found/{item_id}/claim")

    assert response.status_code == 302

    with app.app_context():
        item = db.session.get(LostFoundItem, item_id)
        student = Student.query.filter_by(email="student@gmail.com").first()
        assert item.status == "Claimed"
        assert item.claimant_id == student.id


def test_reporter_can_mark_claimed_item_returned(logged_in_client, app):
    with app.app_context():
        student = Student.query.filter_by(email="student@gmail.com").first()
        other_student = Student(
            full_name="Claimant Student",
            email="claimant@gmail.com",
            password_hash=generate_password_hash("ClaimPass123!"),
            contact_number="9876543214",
            srn="CLAIM123",
            parent_name="Claimant Parent",
            parent_contact_number="9876543215",
            hostel_name="Test Hostel",
            room_number="103",
            id_proof_filename="claimant-proof.pdf",
        )
        db.session.add(other_student)
        db.session.commit()

        item = LostFoundItem(
            student_id=student.id,
            item_type="Found",
            title="Silver Keys",
            description="Keys found in the hallway.",
            location="Hallway",
            item_date=date.today(),
            status="Claimed",
            claimant_id=other_student.id,
        )
        db.session.add(item)
        db.session.commit()
        item_id = item.id

    response = logged_in_client.post(f"/lost-found/{item_id}/return")

    assert response.status_code == 302

    with app.app_context():
        item = db.session.get(LostFoundItem, item_id)
        assert item.status == "Returned"
