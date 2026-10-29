from datetime import time

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app import db
from app.models import MessMenu
from app.warden_routes import warden_required


mess_menu_bp = Blueprint(
    "mess_menu",
    __name__,
    url_prefix="/warden/mess-menu",
)

WEEKDAYS = [
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
]
MEAL_TYPES = ["Breakfast", "Lunch", "Snacks", "Dinner"]


@mess_menu_bp.route("/", methods=["GET", "POST"])
@warden_required
def manage_menu():
    if request.method == "POST":
        day = request.form.get("day_of_week", "")
        meal = request.form.get("meal_type", "")
        items = request.form.get("menu_items", "").strip()

        try:
            start_time = time.fromisoformat(request.form.get("start_time", ""))
            end_time = time.fromisoformat(request.form.get("end_time", ""))
        except ValueError:
            flash("Enter valid meal start and end times.", "error")
            return redirect(url_for("mess_menu.manage_menu"))

        if day not in WEEKDAYS or meal not in MEAL_TYPES:
            flash("Choose a valid day and meal type.", "error")
        elif not items or len(items) > 5000:
            flash("Menu items are required and must be under 5000 characters.", "error")
        elif end_time <= start_time:
            flash("The end time must be later than the start time.", "error")
        elif MessMenu.query.filter_by(day_of_week=day, meal_type=meal).first():
            flash("A menu entry already exists for that day and meal.", "error")
        else:
            db.session.add(
                MessMenu(
                    day_of_week=day,
                    meal_type=meal,
                    menu_items=items,
                    start_time=start_time,
                    end_time=end_time,
                    is_available=True,
                )
            )
            db.session.commit()
            flash("Mess menu entry created.", "success")
            return redirect(url_for("mess_menu.manage_menu"))

    menus = MessMenu.query.all()
    menus.sort(
        key=lambda menu: (
            WEEKDAYS.index(menu.day_of_week) if menu.day_of_week in WEEKDAYS else 7,
            MEAL_TYPES.index(menu.meal_type) if menu.meal_type in MEAL_TYPES else 4,
        )
    )
    return render_template(
        "warden_mess_menu.html",
        menus=menus,
        weekdays=WEEKDAYS,
        meal_types=MEAL_TYPES,
    )


@mess_menu_bp.route("/<int:menu_id>/update", methods=["POST"])
@warden_required
def update_menu(menu_id):
    menu = MessMenu.query.get_or_404(menu_id)

    day = request.form.get("day_of_week", "")
    meal = request.form.get("meal_type", "")
    items = request.form.get("menu_items", "").strip()

    try:
        start_time = time.fromisoformat(request.form.get("start_time", ""))
        end_time = time.fromisoformat(request.form.get("end_time", ""))
    except ValueError:
        flash("Enter valid meal start and end times.", "error")
        return redirect(url_for("mess_menu.manage_menu"))

    duplicate = MessMenu.query.filter(
        MessMenu.day_of_week == day,
        MessMenu.meal_type == meal,
        MessMenu.id != menu.id,
    ).first()

    if day not in WEEKDAYS or meal not in MEAL_TYPES:
        flash("Choose a valid day and meal type.", "error")
    elif not items or len(items) > 5000:
        flash("Menu items are required and must be under 5000 characters.", "error")
    elif end_time <= start_time:
        flash("The end time must be later than the start time.", "error")
    elif duplicate:
        flash("Another menu entry already exists for that day and meal.", "error")
    else:
        menu.day_of_week = day
        menu.meal_type = meal
        menu.menu_items = items
        menu.start_time = start_time
        menu.end_time = end_time
        menu.is_available = request.form.get("is_available") == "on"
        db.session.commit()
        flash("Mess menu entry updated.", "success")

    return redirect(url_for("mess_menu.manage_menu"))


@mess_menu_bp.route("/<int:menu_id>/delete", methods=["POST"])
@warden_required
def delete_menu(menu_id):
    menu = MessMenu.query.get_or_404(menu_id)

    if menu.registrations:
        flash("This menu entry has registrations and cannot be deleted.", "error")
    else:
        db.session.delete(menu)
        db.session.commit()
        flash("Mess menu entry deleted.", "success")

    return redirect(url_for("mess_menu.manage_menu"))
