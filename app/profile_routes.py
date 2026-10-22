
import re
from pathlib import Path
from uuid import uuid4

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

from app import db
from app.models import Student


profile_bp = Blueprint("profile", __name__, url_prefix="/profile")

ALLOWED_PHOTO_EXTENSIONS = {"jpg", "jpeg", "png"}
MAX_PHOTO_SIZE = 2 * 1024 * 1024
NAME_PATTERN = r"[A-Za-z]+(?:[ '-][A-Za-z]+)*"


def get_profile_photo():
    """Return the current student's stored profile photo filename."""
    upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
    matches = sorted(
        upload_folder.glob(f"profile_{current_user.id}_*")
    )

    for photo_path in matches:
        if photo_path.is_file():
            return photo_path.name

    return None


def render_profile(form_data=None, errors=None, status=200):
    return (
        render_template(
            "student_profile.html",
            student=current_user,
            form_data=form_data or {},
            errors=errors or {},
            profile_photo=get_profile_photo(),
        ),
        status,
    )


@profile_bp.route("/", methods=["GET"])
@login_required
def view_profile():
    return render_profile()


@profile_bp.route("/edit", methods=["POST"])
@login_required
def edit_profile():
    data = {
        "full_name": request.form.get("full_name", "").strip(),
        "email": request.form.get("email", "").strip().lower(),
        "contact_number": request.form.get(
            "contact_number", ""
        ).strip(),
        "parent_name": request.form.get(
            "parent_name", ""
        ).strip(),
        "parent_contact_number": request.form.get(
            "parent_contact_number", ""
        ).strip(),
    }

    errors = {}

    if not re.fullmatch(NAME_PATTERN, data["full_name"]):
        errors["full_name"] = "Enter a valid name."

    if not re.fullmatch(
        r"[A-Za-z0-9._%+-]+@gmail\.com",
        data["email"],
        re.IGNORECASE,
    ):
        errors["email"] = "Enter a valid Gmail address."

    for field in ("contact_number", "parent_contact_number"):
        if not re.fullmatch(r"[0-9]{10}", data[field]):
            errors[field] = "Enter exactly 10 digits."

    if not re.fullmatch(NAME_PATTERN, data["parent_name"]):
        errors["parent_name"] = "Enter a valid parent name."

    existing_email = Student.query.filter(
        Student.email == data["email"],
        Student.id != current_user.id,
    ).first()

    if existing_email:
        errors["email"] = "This email is already registered."

    if errors:
        return render_profile(data, errors, 400)

    try:
        current_user.full_name = data["full_name"]
        current_user.email = data["email"]
        current_user.contact_number = data["contact_number"]
        current_user.parent_name = data["parent_name"]
        current_user.parent_contact_number = (
            data["parent_contact_number"]
        )

        db.session.commit()

    except IntegrityError:
        db.session.rollback()
        return render_profile(
            data,
            {"general": "The email address is already in use."},
            409,
        )

    flash("Your profile has been updated.", "success")
    return redirect(url_for("profile.view_profile"))


@profile_bp.route("/photo", methods=["POST"])
@login_required
def upload_profile_photo():
    photo = request.files.get("profile_photo")

    if not photo or not photo.filename:
        flash("Choose a photo to upload.", "error")
        return redirect(url_for("profile.view_profile"))

    original_name = secure_filename(photo.filename)
    extension = (
        original_name.rsplit(".", 1)[-1].lower()
        if "." in original_name
        else ""
    )

    if extension not in ALLOWED_PHOTO_EXTENSIONS:
        flash("Upload a JPG, JPEG, or PNG image.", "error")
        return redirect(url_for("profile.view_profile"))

    content = photo.read(MAX_PHOTO_SIZE + 1)

    if not content:
        flash("The selected photo is empty.", "error")
        return redirect(url_for("profile.view_profile"))

    if len(content) > MAX_PHOTO_SIZE:
        flash("The photo must be 2 MB or smaller.", "error")
        return redirect(url_for("profile.view_profile"))

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
    upload_folder.mkdir(parents=True, exist_ok=True)

    filename = f"profile_{current_user.id}_{uuid4().hex}.{extension}"
    destination = upload_folder / filename

    try:
        destination.write_bytes(content)
    except OSError:
        current_app.logger.exception("Profile photo upload failed.")
        flash("Photo upload failed. Please try again.", "error")
        return redirect(url_for("profile.view_profile"))

    # Remove only this student's previous profile photos.
    for old_path in upload_folder.glob(
        f"profile_{current_user.id}_*"
    ):
        if old_path != destination and old_path.is_file():
            old_path.unlink(missing_ok=True)

    flash("Profile photo updated.", "success")
    return redirect(url_for("profile.view_profile"))
