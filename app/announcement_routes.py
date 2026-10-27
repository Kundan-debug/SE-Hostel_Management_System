from flask import abort, Blueprint, flash, redirect, render_template, request, url_for

from datetime import datetime, timezone
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import or_
from app import db
from app.models import Announcement
from app.warden_routes import warden_required

announcement_bp = Blueprint("announcement", __name__, url_prefix="/announcements")

@announcement_bp.route("/")
@login_required
def view_announcements():
    now = datetime.now(timezone.utc)
    items = (Announcement.query.filter(or_(Announcement.expires_at.is_(None),
        Announcement.expires_at > now)).order_by(Announcement.published_at.desc()).all())
    return render_template("announcements.html", announcements=items)

@announcement_bp.route("/manage", methods=["GET", "POST"])
@warden_required
def manage_announcements():
    errors = {}
    form_data = {}
    if request.method == "POST":
        form_data = request.form
        title = request.form.get("title", "").strip()
        message = request.form.get("message", "").strip()
        category = request.form.get("category", "General").strip() or "General"
        expiry = request.form.get("expires_at", "").strip()
        expires_at = None
        if not title or len(title) > 150:
            errors["title"] = "Enter a title of at most 150 characters."
        if not message:
            errors["message"] = "Enter a message."
        if len(category) > 30:
            errors["category"] = "Category must be at most 30 characters."
        if expiry:
            try:
                expires_at = datetime.strptime(expiry, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
                if expires_at <= datetime.now(timezone.utc):
                    errors["expires_at"] = "Expiry must be in the future."
            except ValueError:
                errors["expires_at"] = "Enter a valid expiry date and time."
        if not errors:
            db.session.add(Announcement(title=title, message=message, category=category, expires_at=expires_at))
            db.session.commit()
            flash("Announcement published.", "success")
            return redirect(url_for("announcement.manage_announcements"))
    items = Announcement.query.order_by(Announcement.published_at.desc()).all()
    return render_template("manage_announcements.html", announcements=items, errors=errors, form_data=form_data)

@announcement_bp.route("/<int:announcement_id>/edit", methods=["POST"])
@warden_required
def edit_announcement(announcement_id):
    item = db.session.get(Announcement, announcement_id)
    if item is None:
        abort(404)
    title = request.form.get("title", "").strip()
    message = request.form.get("message", "").strip()
    category = request.form.get("category", "General").strip() or "General"
    expiry = request.form.get("expires_at", "").strip()
    if not title or len(title) > 150 or not message or len(category) > 30:
        flash("Enter a valid title, message, and category.", "error")
        return redirect(url_for("announcement.manage_announcements"))
    expires_at = None
    if expiry:
        try:
            expires_at = datetime.strptime(expiry, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
            if expires_at <= datetime.now(timezone.utc):
                flash("Expiry must be in the future.", "error")
                return redirect(url_for("announcement.manage_announcements"))
        except ValueError:
            flash("Enter a valid expiry date and time.", "error")
            return redirect(url_for("announcement.manage_announcements"))
    item.title, item.message, item.category, item.expires_at = title, message, category, expires_at
    db.session.commit()
    flash("Announcement updated.", "success")
    return redirect(url_for("announcement.manage_announcements"))

@announcement_bp.route("/<int:announcement_id>/delete", methods=["POST"])
@warden_required
def delete_announcement(announcement_id):
    item = db.session.get(Announcement, announcement_id)
    if item is None:
        bort(404)
    db.session.delete(item)
    db.session.commit()
    flash("Announcement deleted.", "success")
    return redirect(url_for("announcement.manage_announcements"))
