
from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models import LeaveApplication

leave_bp = Blueprint("leave", __name__, url_prefix="/leave")


@leave_bp.route("/", methods=["GET", "POST"])
@login_required
def apply_leave():
    if request.method == "POST":
        leave_type = request.form.get("leave_type", "").strip()
        start_text = request.form.get("start_date", "").strip()
        end_text = request.form.get("end_date", "").strip()
        reason = request.form.get("reason", "").strip()

        if leave_type not in {"Personal", "Medical", "Emergency", "Other"}:
            flash("Please select a valid leave type.", "error")
            return redirect(url_for("leave.apply_leave"))

        if not start_text or not end_text or not reason:
            flash("Please complete all required fields.", "error")
            return redirect(url_for("leave.apply_leave"))

        try:
            start_date = date.fromisoformat(start_text)
            end_date = date.fromisoformat(end_text)
        except ValueError:
            flash("Please enter valid dates.", "error")
            return redirect(url_for("leave.apply_leave"))

        if start_date < date.today() or end_date < start_date:
            flash("Please choose a valid date range.", "error")
            return redirect(url_for("leave.apply_leave"))

        application = LeaveApplication(
            student_id=current_user.id,
            leave_type=leave_type,
            start_date=start_date,
            end_date=end_date,
            reason=reason,
            status="Pending",
        )
        db.session.add(application)
        db.session.commit()

        flash("Leave application submitted successfully.", "success")
        return redirect(url_for("leave.apply_leave"))

    applications = (
        LeaveApplication.query
        .filter_by(student_id=current_user.id)
        .order_by(LeaveApplication.created_at.desc())
        .all()
    )

    return render_template(
        "apply_leave.html",
        applications=applications,
    )


@leave_bp.route("/<int:application_id>/cancel", methods=["POST"])
@login_required
def cancel_leave(application_id):
    application = LeaveApplication.query.filter_by(
        id=application_id,
        student_id=current_user.id,
    ).first_or_404()

    if application.status != "Pending":
        flash("Only pending applications can be cancelled.", "error")
    else:
        application.status = "Cancelled"
        db.session.commit()
        flash("Leave application cancelled.", "success")

    return redirect(url_for("leave.apply_leave"))
