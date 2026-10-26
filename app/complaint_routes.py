from pathlib import Path
from uuid import uuid4

from flask import (
    Blueprint,
    current_app,
    flash,
    render_template,
    request,
    redirect,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app import ALLOWED_EXTENSIONS, MAX_FILE_SIZE, db
from app.models import (
    COMPLAINT_CATEGORIES,
    COMPLAINT_PRIORITIES,
    COMPLAINT_STATUSES,
    Complaint,
)

complaint_bp = Blueprint("complaint", __name__, url_prefix="/complaints")

MIN_DESCRIPTION_LENGTH = 10
MAX_DESCRIPTION_LENGTH = 1000


def complaint_folder():
    folder = Path(current_app.config["UPLOAD_FOLDER"]) / "complaints"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def validate_attachment(attachment):
    """Return (error, original_name, extension) for an optional upload."""
    if not attachment or not attachment.filename:
        return None, "", ""

    original_name = secure_filename(attachment.filename)
    extension = (
        original_name.rsplit(".", 1)[-1].lower()
        if "." in original_name
        else ""
    )

    if extension not in ALLOWED_EXTENSIONS:
        return "Attach a PDF, JPG, JPEG, or PNG file.", "", ""

    if len(attachment.read()) > MAX_FILE_SIZE:
        return "The attachment must be 5 MB or smaller.", "", ""

    attachment.seek(0)
    return None, original_name, extension


def render_complaints(status_filter="", form_data=None, http_status=200):
    query = Complaint.query.filter_by(student_id=current_user.id)

    if status_filter in COMPLAINT_STATUSES:
        query = query.filter_by(status=status_filter)
    else:
        status_filter = ""

    complaints = query.order_by(
        Complaint.created_at.desc(),
        Complaint.id.desc(),
    ).all()

    return render_template(
        "complaints.html",
        complaints=complaints,
        categories=COMPLAINT_CATEGORIES,
        priorities=COMPLAINT_PRIORITIES,
        statuses=COMPLAINT_STATUSES,
        status_filter=status_filter,
        form_data=form_data or {},
        max_description=MAX_DESCRIPTION_LENGTH,
    ), http_status


@complaint_bp.route("/", methods=["GET", "POST"])
@login_required
def submit_complaint():
    if request.method == "GET":
        return render_complaints(request.args.get("status", "").strip())

    category = request.form.get("category", "").strip()
    priority = request.form.get("priority", "").strip()
    description = request.form.get("description", "").strip()
    form_data = {
        "category": category,
        "priority": priority,
        "description": description,
    }

    errors = []

    if category not in COMPLAINT_CATEGORIES:
        errors.append("Please select a valid complaint category.")

    if priority not in COMPLAINT_PRIORITIES:
        errors.append("Please select a valid priority.")

    if not description:
        errors.append("Please describe your complaint.")
    elif len(description) < MIN_DESCRIPTION_LENGTH:
        errors.append(
            "The description must be at least "
            f"{MIN_DESCRIPTION_LENGTH} characters."
        )
    elif len(description) > MAX_DESCRIPTION_LENGTH:
        errors.append(
            "The description must be at most "
            f"{MAX_DESCRIPTION_LENGTH} characters."
        )

    attachment = request.files.get("attachment")
    attachment_error, original_name, extension = validate_attachment(
        attachment
    )
    if attachment_error:
        errors.append(attachment_error)

    if errors:
        for message in errors:
            flash(message, "error")
        return render_complaints(form_data=form_data, http_status=400)

    saved_name = None
    saved_path = None

    if extension:
        saved_name = f"{uuid4().hex}.{extension}"
        saved_path = complaint_folder() / saved_name

    try:
        if saved_path:
            attachment.save(saved_path)

        db.session.add(
            Complaint(
                student_id=current_user.id,
                category=category,
                priority=priority,
                description=description,
                attachment_filename=saved_name,
                attachment_name=original_name or None,
                status="Open",
            )
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        if saved_path:
            saved_path.unlink(missing_ok=True)
        current_app.logger.exception("Complaint submission failed.")
        flash("Your complaint could not be submitted. Please try again.", "error")
        return render_complaints(form_data=form_data, http_status=500)

    flash("Complaint submitted successfully.", "success")
    return redirect(url_for("complaint.submit_complaint"))


@complaint_bp.route("/<int:complaint_id>/attachment")
@login_required
def download_attachment(complaint_id):
    complaint = Complaint.query.filter_by(
        id=complaint_id,
        student_id=current_user.id,
    ).first_or_404()

    if not complaint.attachment_filename:
        return redirect(url_for("complaint.submit_complaint"))

    return send_from_directory(
        complaint_folder(),
        complaint.attachment_filename,
        as_attachment=True,
        download_name=complaint.attachment_name or complaint.attachment_filename,
    )
