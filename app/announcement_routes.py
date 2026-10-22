
from datetime import datetime, timezone

from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import or_

from app import db
from app.models import Announcement

announcement_bp = Blueprint(
    "announcement",
    __name__,
    url_prefix="/announcements",
)


@announcement_bp.route("/")
@login_required
def view_announcements():
    now = datetime.now(timezone.utc)

    announcements = (
        Announcement.query
        .filter(
            or_(
                Announcement.expires_at.is_(None),
                Announcement.expires_at > now,
            )
        )
        .order_by(Announcement.published_at.desc())
        .all()
    )

    return render_template(
        "announcements.html",
        announcements=announcements,
    )
