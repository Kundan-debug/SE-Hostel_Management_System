from flask import Blueprint, render_template
from flask_login import current_user, login_required

from app.models import Room

room_bp = Blueprint("room", __name__, url_prefix="/room-details")


@room_bp.route("/")
@login_required
def room_details():
    room = Room.query.filter_by(
        hostel_name=current_user.hostel_name,
        room_number=current_user.room_number,
    ).first()

    return render_template(
        "room_details.html",
        student=current_user,
        room=room,
    )
