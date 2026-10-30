from datetime import date
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
from sqlalchemy import or_
from werkzeug.utils import secure_filename

from app import ALLOWED_EXTENSIONS, MAX_FILE_SIZE, db
from app.models import LostFoundItem

lost_found_bp = Blueprint(
    "lost_found",
    __name__,
    url_prefix="/lost-found",
)


def valid_image_content(photo, extension):
    photo.seek(0)
    header = photo.read(8)
    photo.seek(0)

    if extension in {"jpg", "jpeg"}:
        return header.startswith(b"\\xff\\xd8\\xff")
    if extension == "png":
        return header == b"\\x89PNG\\r\\n\\x1a\\n"
    return False


def photo_folder():
    folder = Path(current_app.config["UPLOAD_FOLDER"]) / "lost_found"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


@lost_found_bp.route("/", methods=["GET"])
@login_required
def list_items():
    query = request.args.get("q", "").strip()
    item_type = request.args.get("type", "").strip()
    status = request.args.get("status", "").strip()

    items_query = LostFoundItem.query

    if query:
        pattern = f"%{query}%"
        items_query = items_query.filter(
            or_(
                LostFoundItem.title.ilike(pattern),
                LostFoundItem.description.ilike(pattern),
                LostFoundItem.location.ilike(pattern),
            )
        )

    if item_type in ("Lost", "Found"):
        items_query = items_query.filter_by(item_type=item_type)

    if status in ("Open", "Claimed", "Returned"):
        items_query = items_query.filter_by(status=status)

    items = items_query.order_by(
        LostFoundItem.created_at.desc(),
        LostFoundItem.id.desc(),
    ).all()

    return render_template(
        "lost_found.html",
        items=items,
        query=query,
        item_type=item_type,
        status=status,
    )


@lost_found_bp.route("/report", methods=["POST"])
@login_required
def report_item():
    item_type = request.form.get("item_type", "").strip()
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    location = request.form.get("location", "").strip()
    item_date_text = request.form.get("item_date", "").strip()
    photo = request.files.get("photo")

    errors = []

    if item_type not in ("Lost", "Found"):
        errors.append("Select Lost or Found.")
    if not title or len(title) > 100:
        errors.append("Enter a title of up to 100 characters.")
    if not description or len(description) > 1000:
        errors.append("Enter a description of up to 1000 characters.")
    if not location or len(location) > 150:
        errors.append("Enter a location of up to 150 characters.")

    try:
        item_date = date.fromisoformat(item_date_text)
    except ValueError:
        item_date = None
        errors.append("Enter a valid date.")

    original_name = secure_filename(photo.filename) if photo and photo.filename else ""
    extension = (
        original_name.rsplit(".", 1)[-1].lower()
        if "." in original_name
        else ""
    )

    if original_name and extension not in {"jpg", "jpeg", "png"}:
        errors.append("Photos must be JPG, JPEG, or PNG files.")
    elif original_name:
        if len(photo.read()) > MAX_FILE_SIZE:
            errors.append("The photo must be 5 MB or smaller.")
        photo.seek(0)
        if not valid_image_content(photo, extension):
            errors.append("The uploaded file must contain a valid JPEG or PNG image.")

    if errors:
        for error in errors:
            flash(error, "error")
        return redirect(url_for("lost_found.list_items")), 400

    saved_name = None
    saved_path = None

    if original_name:
        saved_name = f"{uuid4().hex}.{extension}"
        saved_path = photo_folder() / saved_name

    try:
        if saved_path:
            photo.save(saved_path)

        item = LostFoundItem(
            student_id=current_user.id,
            item_type=item_type,
            title=title,
            description=description,
            location=location,
            item_date=item_date,
            photo_filename=saved_name,
            status="Open",
        )
        db.session.add(item)
        db.session.commit()
    except Exception:
        db.session.rollback()
        if saved_path:
            saved_path.unlink(missing_ok=True)
        current_app.logger.exception("Lost and Found report failed.")
        flash("Could not submit the report. Please try again.", "error")
        return redirect(url_for("lost_found.list_items")), 500

    flash("Item reported successfully.", "success")
    return redirect(url_for("lost_found.list_items"))


@lost_found_bp.route("/<int:item_id>/claim", methods=["POST"])
@login_required
def claim_item(item_id):
    from flask import abort
    from sqlalchemy import update

    try:
        result = db.session.execute(
            update(LostFoundItem)
            .where(
                LostFoundItem.id == item_id,
                LostFoundItem.student_id != current_user.id,
                LostFoundItem.item_type == "Found",
                LostFoundItem.status == "Open",
            )
            .values(claimant_id=current_user.id, status="Claimed")
        )

        if result.rowcount == 1:
            db.session.commit()
            flash("Claim submitted successfully.", "success")
        else:
            db.session.rollback()
            item = db.session.get(LostFoundItem, item_id)
            if item is None:
                abort(404)
            if item.student_id == current_user.id:
                flash("You cannot claim your own report.", "error")
            else:
                flash("This item cannot be claimed.", "error")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Lost and Found claim failed.")
        flash("Could not claim the item. Please try again.", "error")

    return redirect(url_for("lost_found.list_items"))


@lost_found_bp.route("/<int:item_id>/return", methods=["POST"])
@login_required
def mark_returned(item_id):
    from flask import abort

    item = db.session.get(LostFoundItem, item_id)
    if item is None:
        abort(404)

    if item.student_id != current_user.id:
        flash("Only the person who reported the item can mark it returned.", "error")
        return redirect(url_for("lost_found.list_items"))

    if item.status != "Claimed":
        flash("Only claimed items can be marked returned.", "error")
        return redirect(url_for("lost_found.list_items"))

    try:
        item.status = "Returned"
        db.session.commit()
        flash("Item marked as returned.", "success")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Lost and Found return failed.")
        flash("Could not mark the item returned. Please try again.", "error")

    return redirect(url_for("lost_found.list_items"))
