from flask import Blueprint, render_template, request
from flask_login import current_user, login_required

from app import db
from app.models import Room

room_bp = Blueprint("room", __name__, url_prefix="/room-details")


def get_student_room(student):
    """Return the Room record matching the student's hostel and room."""
    return Room.query.filter_by(
        hostel_name=student.hostel_name,
        room_number=student.room_number,
    ).first()


def room_state(room, student):
    """Classify a room from the point of view of one student (read-only view).

    Returns one of: "current", "maintenance", "full", "vacant".
    """
    if (
        room.hostel_name == student.hostel_name
        and room.room_number == student.room_number
    ):
        return "current"
    if room.maintenance_status != "Available":
        return "maintenance"
    if room.available_beds <= 0:
        return "full"
    return "vacant"


@room_bp.route("/")
@login_required
def room_details():
    room = get_student_room(current_user)

    return render_template(
        "room_details.html",
        student=current_user,
        room=room,
    )


@room_bp.route("/allocation")
@login_required
def room_allocation():
    hostel_filter = request.args.get("hostel", "").strip()

    query = Room.query
    if hostel_filter:
        query = query.filter_by(hostel_name=hostel_filter)

    rooms = query.order_by(Room.hostel_name, Room.room_number).all()
    rows = [
        {"room": room, "state": room_state(room, current_user)}
        for room in rooms
    ]

    hostels = [
        name
        for (name,) in db.session.query(Room.hostel_name)
        .distinct()
        .order_by(Room.hostel_name)
        .all()
    ]

    return render_template(
        "room_allocation.html",
        student=current_user,
        current_room=get_student_room(current_user),
        rows=rows,
        hostels=hostels,
        hostel_filter=hostel_filter,
    )
