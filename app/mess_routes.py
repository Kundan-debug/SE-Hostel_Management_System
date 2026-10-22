
from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import (
    MessMenu,
    MealRegistration,
    MessAttendance,
    MessFeedback,
    MessHoliday,
    MessFee,
)

mess_bp = Blueprint("mess", __name__, url_prefix="/mess")

WEEKDAYS = [
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
]

MEAL_TYPES = ["Breakfast", "Lunch", "Snacks", "Dinner"]


@mess_bp.route("/", methods=["GET"])
@login_required
def manage_mess():
    menus = (
        MessMenu.query
        .filter_by(is_available=True)
        .all()
    )
    weekday_order = {day: index for index, day in enumerate(WEEKDAYS)}
    meal_order = {meal: index for index, meal in enumerate(MEAL_TYPES)}
    menus.sort(
        key=lambda menu: (
            weekday_order.get(menu.day_of_week, 7),
            meal_order.get(menu.meal_type, 4),
        )
    )

    registrations = MealRegistration.query.filter_by(
        student_id=current_user.id
    ).all()
    registered_menu_ids = {item.menu_id for item in registrations}

    attendance = (
        MessAttendance.query
        .filter_by(student_id=current_user.id)
        .order_by(MessAttendance.attendance_date.desc())
        .all()
    )

    feedback_items = (
        MessFeedback.query
        .filter_by(student_id=current_user.id)
        .order_by(MessFeedback.created_at.desc())
        .all()
    )

    holidays = (
        MessHoliday.query
        .filter(MessHoliday.holiday_date >= date.today())
        .order_by(MessHoliday.holiday_date.asc())
        .all()
    )

    fees = (
        MessFee.query
        .filter_by(student_id=current_user.id)
        .order_by(MessFee.billing_month.desc())
        .all()
    )

    return render_template(
        "mess.html",
        menus=menus,
        registered_menu_ids=registered_menu_ids,
        attendance=attendance,
        feedback_items=feedback_items,
        holidays=holidays,
        fees=fees,
        weekdays=WEEKDAYS,
    )


@mess_bp.route("/register", methods=["POST"])
@login_required
def register_meal():
    menu_id = request.form.get("menu_id", type=int)

    if menu_id is None:
        flash("Please select a valid meal.", "error")
        return redirect(url_for("mess.manage_mess"))

    menu = db.session.get(MessMenu, menu_id)

    if not menu or not menu.is_available:
        flash("That meal is currently unavailable for registration.", "error")
        return redirect(url_for("mess.manage_mess"))

    existing = MealRegistration.query.filter_by(
        student_id=current_user.id,
        menu_id=menu.id,
    ).first()

    if existing:
        flash("You are already registered for this meal.", "info")
        return redirect(url_for("mess.manage_mess"))

    registration = MealRegistration(
        student_id=current_user.id,
        menu_id=menu.id,
    )
    db.session.add(registration)

    try:
        db.session.commit()
        flash("Meal registration successful.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("You are already registered for this meal.", "info")

    return redirect(url_for("mess.manage_mess"))


@mess_bp.route("/feedback", methods=["POST"])
@login_required
def submit_feedback():
    category = request.form.get("category", "").strip()
    message = request.form.get("message", "").strip()

    if category not in {"Feedback", "Complaint"}:
        flash("Select Feedback or Complaint.", "error")
        return redirect(url_for("mess.manage_mess"))

    if not message or len(message) > 1000:
        flash("Enter a message of 1 to 1000 characters.", "error")
        return redirect(url_for("mess.manage_mess"))

    item = MessFeedback(
        student_id=current_user.id,
        category=category,
        message=message,
    )
    db.session.add(item)
    db.session.commit()

    flash("Your submission has been recorded.", "success")
    return redirect(url_for("mess.manage_mess"))
