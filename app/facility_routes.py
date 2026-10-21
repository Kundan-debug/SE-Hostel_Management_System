
from datetime import date, datetime

from flask import (
    Blueprint,
    jsonify,
    request,
    render_template,
)
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import CommonFacility, FacilityBooking


facility_bp = Blueprint(
    "facility",
    __name__,
    url_prefix="/facilities",
)


# Common Facility Booking page

@facility_bp.route("/page", methods=["GET"])
@login_required
def facility_booking_page():
    return render_template("facility_booking.html")


# List all facilities

@facility_bp.route("/", methods=["GET"])
@login_required
def list_facilities():
    facilities = CommonFacility.query.order_by(
        CommonFacility.name
    ).all()

    return jsonify([
        {
            "id": facility.id,
            "name": facility.name,
            "description": facility.description,
            "location": facility.location,
            "capacity": facility.capacity,
            "is_available": facility.is_available,
        }
        for facility in facilities
    ]), 200


# View the logged-in student's booking history

@facility_bp.route("/bookings", methods=["GET"])
@login_required
def list_my_bookings():
    bookings = FacilityBooking.query.filter_by(
        student_id=current_user.id
    ).order_by(
        FacilityBooking.booking_date.desc(),
        FacilityBooking.start_time.desc(),
    ).all()

    return jsonify([
        {
            "id": booking.id,
            "facility_id": booking.facility_id,
            "facility_name": booking.facility.name,
            "booking_date": booking.booking_date.isoformat(),
            "start_time": booking.start_time.strftime("%H:%M"),
            "end_time": booking.end_time.strftime("%H:%M"),
            "status": booking.status,
            "created_at": (
                booking.created_at.isoformat()
                if booking.created_at
                else None
            ),
        }
        for booking in bookings
    ]), 200


# Create a facility booking

@facility_bp.route("/bookings", methods=["POST"])
@login_required
def create_booking():
    data = request.get_json(silent=True) or {}

    required = (
        "facility_id",
        "booking_date",
        "start_time",
        "end_time",
    )

    missing = [
        field for field in required
        if not data.get(field)
    ]

    if missing:
        return jsonify({
            "error": "Missing required fields.",
            "fields": missing,
        }), 400

    try:
        facility_id = int(data["facility_id"])

        booking_date = date.fromisoformat(
            data["booking_date"]
        )

        start_time = datetime.strptime(
            data["start_time"], "%H:%M"
        ).time()

        end_time = datetime.strptime(
            data["end_time"], "%H:%M"
        ).time()

    except (TypeError, ValueError):
        return jsonify({
            "error": (
                "Invalid input. Use an integer facility_id, "
                "YYYY-MM-DD date, and HH:MM times."
            )
        }), 400

    if booking_date < date.today():
        return jsonify({
            "error": "Bookings cannot be made for past dates."
        }), 400

    if end_time <= start_time:
        return jsonify({
            "error": "End time must be later than start time."
        }), 400

    facility = db.session.get(
        CommonFacility,
        facility_id,
    )

    if facility is None:
        return jsonify({
            "error": "Facility not found."
        }), 404

    if not facility.is_available:
        return jsonify({
            "error": "This facility is currently unavailable."
        }), 409

    overlapping = FacilityBooking.query.filter(
        FacilityBooking.facility_id == facility_id,
        FacilityBooking.booking_date == booking_date,
        FacilityBooking.status.in_([
            "Pending",
            "Confirmed",
        ]),
        FacilityBooking.start_time < end_time,
        FacilityBooking.end_time > start_time,
    ).count()

    if overlapping >= facility.capacity:
        return jsonify({
            "error": (
                "No capacity is available for this time slot."
            )
        }), 409

    booking = FacilityBooking(
        student_id=current_user.id,
        facility_id=facility_id,
        booking_date=booking_date,
        start_time=start_time,
        end_time=end_time,
        status="Pending",
    )

    try:
        db.session.add(booking)
        db.session.commit()

    except IntegrityError:
        db.session.rollback()

        return jsonify({
            "error": "Unable to create this booking."
        }), 409

    return jsonify({
        "message": "Booking request submitted successfully.",
        "booking": {
            "id": booking.id,
            "facility_id": booking.facility_id,
            "facility_name": facility.name,
            "booking_date": booking.booking_date.isoformat(),
            "start_time": booking.start_time.strftime("%H:%M"),
            "end_time": booking.end_time.strftime("%H:%M"),
            "status": booking.status,
        },
    }), 201


# Cancel a booking belonging to the logged-in student

@facility_bp.route(
    "/bookings/<int:booking_id>/cancel",
    methods=["POST"],
)
@login_required
def cancel_booking(booking_id):
    booking = db.session.get(
        FacilityBooking,
        booking_id,
    )

    if (
        booking is None
        or booking.student_id != current_user.id
    ):
        return jsonify({
            "error": "Booking not found."
        }), 404

    if booking.status == "Cancelled":
        return jsonify({
            "error": "This booking is already cancelled."
        }), 409

    booking.status = "Cancelled"

    try:
        db.session.commit()

    except IntegrityError:
        db.session.rollback()

        return jsonify({
            "error": "Unable to cancel this booking."
        }), 409

    return jsonify({
        "message": "Booking cancelled successfully.",
        "booking_id": booking.id,
        "status": booking.status,
    }), 200
