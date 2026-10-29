"""Warden-only room and complaint management."""
from functools import wraps

from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models import Room, Complaint, Student, Fee, Payment, LeaveApplication, COMPLAINT_PRIORITIES, COMPLAINT_STATUSES

warden_bp = Blueprint("warden", __name__, url_prefix="/warden")


def warden_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not getattr(current_user, "is_warden", False):
            abort(403)
        return view(*args, **kwargs)
    return wrapped


@warden_bp.route("/")
@warden_required
def dashboard():
    return render_template(
        "warden_dashboard.html",
        room_count=Room.query.count(),
        student_count=Student.query.count(),
        open_complaints=Complaint.query.filter(Complaint.status != "Resolved").count(),
    )


@warden_bp.route("/rooms", methods=["GET", "POST"])
@warden_required
def rooms():
    if request.method == "POST":
        hostel = request.form.get("hostel_name", "").strip()
        number = request.form.get("room_number", "").strip()
        try:
            capacity = int(request.form.get("capacity", ""))
        except ValueError:
            capacity = 0
        if not hostel or not number or capacity < 1:
            flash("Enter a hostel, room number, and positive capacity.", "error")
        elif Room.query.filter_by(hostel_name=hostel, room_number=number).first():
            flash("That room already exists in this hostel.", "error")
        else:
            db.session.add(Room(hostel_name=hostel, room_number=number, capacity=capacity,
                                occupied_beds=0, maintenance_status="Available"))
            db.session.commit()
            flash("Room created.", "success")
            return redirect(url_for("warden.rooms"))

    all_rooms = Room.query.order_by(Room.hostel_name, Room.room_number).all()
    hostels = sorted({r.hostel_name for r in all_rooms})
    return render_template("warden_rooms.html", rooms=all_rooms, hostels=hostels)


@warden_bp.route("/rooms/<int:room_id>/update", methods=["POST"])
@warden_required
def update_room(room_id):
    room = Room.query.get_or_404(room_id)
    status = request.form.get("maintenance_status", "")
    if status not in ("Available", "Under Maintenance"):
        abort(400)
    room.maintenance_status = status
    db.session.commit()
    flash("Room status updated.", "success")
    return redirect(url_for("warden.rooms"))


@warden_bp.route("/allocations", methods=["GET", "POST"])
@warden_required
def allocations():
    if request.method == "POST":
        action = request.form.get("action", "")
        try:
            student_id = int(request.form.get("student_id", ""))
            room_id = int(request.form.get("room_id", ""))
        except ValueError:
            flash("Choose a valid student and room.", "error")
            return redirect(url_for("warden.allocations"))
        student = Student.query.get_or_404(student_id)
        room = Room.query.get_or_404(room_id)
        current_room = Room.query.filter_by(
            hostel_name=student.hostel_name, room_number=student.room_number
        ).first()

        if action not in ("allocate", "transfer"):
            abort(400)
        if room.maintenance_status != "Available" or room.available_beds < 1:
            flash("That room is unavailable or full.", "error")
        elif current_room and current_room.id == room.id:
            flash("The student is already assigned to that room.", "error")
        else:
            if current_room:
                current_room.occupied_beds = max(0, current_room.occupied_beds - 1)
            room.occupied_beds += 1
            student.hostel_name = room.hostel_name
            student.room_number = room.room_number
            db.session.commit()
            flash("Room allocation updated.", "success")
        return redirect(url_for("warden.allocations"))

    students = Student.query.order_by(Student.full_name).all()
    rooms = Room.query.order_by(Room.hostel_name, Room.room_number).all()
    return render_template("warden_allocations.html", students=students, rooms=rooms)


@warden_bp.route("/allocations/<int:student_id>/release", methods=["POST"])
@warden_required
def release_allocation(student_id):
    student = Student.query.get_or_404(student_id)
    room = Room.query.filter_by(hostel_name=student.hostel_name, room_number=student.room_number).first()
    if room:
        room.occupied_beds = max(0, room.occupied_beds - 1)
    # Keep required Student hostel/room fields valid; mark the room as unassigned.
    student.hostel_name = "Unassigned"
    student.room_number = "Unassigned"
    db.session.commit()
    flash("Student room assignment released.", "success")
    return redirect(url_for("warden.allocations"))


@warden_bp.route("/complaints", methods=["GET", "POST"])
@warden_required
def complaints():
    if request.method == "POST":
        try:
            complaint = Complaint.query.get_or_404(int(request.form.get("complaint_id", "")))
        except ValueError:
            abort(400)
        status = request.form.get("status", "")
        priority = request.form.get("priority", "")
        if status not in COMPLAINT_STATUSES or priority not in COMPLAINT_PRIORITIES:
            abort(400)
        complaint.status = status
        complaint.priority = priority
        db.session.commit()
        flash("Complaint updated.", "success")
        return redirect(url_for("warden.complaints"))
    items = Complaint.query.order_by(Complaint.created_at.desc()).all()
    return render_template("warden_complaints.html", complaints=items,
                           statuses=COMPLAINT_STATUSES, priorities=COMPLAINT_PRIORITIES)


@warden_bp.route("/fees", methods=["GET", "POST"])
@warden_required
def manage_fee_records():
    if request.method == "POST":
        try:
            student_id = int(request.form.get("student_id", ""))
            amount = Decimal(request.form.get("amount", ""))
            due_date = date.fromisoformat(request.form.get("due_date", ""))
        except (ValueError, InvalidOperation):
            flash("Enter a valid student, amount, and due date.", "error")
            return redirect(url_for("warden.manage_fee_records"))

        student = db.session.get(Student, student_id)
        description = request.form.get("description", "").strip()
        fee_type = request.form.get("fee_type", "").strip()

        if student is None or not description or not fee_type or not amount.is_finite() or amount <= 0:
            flash("Enter valid fee details and select a student.", "error")
        else:
            fee = Fee(
                student_id=student.id,
                description=description,
                fee_type=fee_type,
                amount=amount,
                due_date=due_date,
            )
            db.session.add(fee)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Creating fee record failed")
                flash("Fee record could not be created.", "error")
            else:
                flash("Fee record created successfully.", "success")
                return redirect(url_for("warden.manage_fee_records"))

    students = Student.query.order_by(Student.full_name).all()
    fees = Fee.query.order_by(Fee.due_date.asc()).all()
    return render_template("warden_fees.html", students=students, fees=fees)


@warden_bp.route("/fees/receipts/<int:payment_id>")
@warden_required
def fee_receipt(payment_id):
    payment = db.session.get(Payment, payment_id)
    if payment is None or payment.status != "Success":
        abort(404)
    return render_template("receipt.html", payment=payment)


@warden_bp.route("/leave-requests", methods=["GET", "POST"])
@warden_required
def leave_requests():
    if request.method == "POST":
        application_id = request.form.get("application_id", type=int)
        status = request.form.get("status")

        application = db.session.get(LeaveApplication, application_id)

        if application is None:
            flash("Leave request not found.", "error")
        elif application.status != "Pending":
            flash("This leave request has already been decided.", "error")
        elif status not in ("Approved", "Rejected"):
            flash("Invalid decision.", "error")
        else:
            application.status = status
            db.session.commit()
            flash(f"Leave request {status.lower()}.", "success")

        return redirect(url_for("warden.leave_requests"))

    applications = LeaveApplication.query.order_by(
        LeaveApplication.created_at.desc()
    ).all()

    return render_template(
        "warden_leave_requests.html",
        applications=applications,
    )
