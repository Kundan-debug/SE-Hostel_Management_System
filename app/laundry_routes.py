
from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request, render_template
from flask_login import current_user, login_required

from app import db
from app.models import LaundryRequest

laundry_bp = Blueprint("laundry", __name__, url_prefix="/api/laundry")

VALID_STATUSES = {"pending", "processing", "ready", "delivered", "cancelled"}

@laundry_bp.route("/page", methods=["GET"])
@login_required
def laundry_page():
    return render_template("laundry.html")




def parse_date(value, field_name, required=False):
    if value is None or value == "":
        if required:
            raise ValueError(f"{field_name} is required")
        return None

    if not isinstance(value, str):
        raise ValueError(f"{field_name} must use YYYY-MM-DD format")

    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{field_name} must use YYYY-MM-DD format")


def error(message, status):
    return jsonify({"error": message}), status


def owned_request(request_id):
    item = db.session.get(LaundryRequest, request_id)

    if item is None:
        return None, error("Laundry request not found", 404)

    if str(item.student_id) != str(current_user.id):
        return None, error("Access denied", 403)

    return item, None


@laundry_bp.route("", methods=["POST"])
@login_required
def create_laundry_request():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return error("A JSON object is required", 400)

    # Student identity comes from the authenticated session.
    # Never trust a student_id supplied by the request body.
    item_details = data.get("item_details")

    if not isinstance(item_details, str) or not item_details.strip():
        return error("item_details is required", 400)

    item_details = item_details.strip()

    if len(item_details) > 500:
        return error("item_details exceeds its maximum length", 400)

    quantity = data.get("quantity")
    if type(quantity) is not int or quantity < 1:
        return error("quantity must be a positive integer", 400)

    try:
        pickup_date = parse_date(
            data.get("pickup_date"), "pickup_date", required=True
        )
        delivery_date = parse_date(data.get("delivery_date"), "delivery_date")

        if delivery_date and delivery_date < pickup_date:
            return error("delivery_date cannot be before pickup_date", 400)

    except ValueError as exc:
        return error(str(exc), 400)

    # Charges and payment status must be set by an authorized workflow.
    if "charges" in data or "payment_status" in data:
        return error("Charges and payment status cannot be set by students", 400)

    item = LaundryRequest(
        student_id=str(current_user.id),
        item_details=item_details,
        quantity=quantity,
        pickup_date=pickup_date,
        delivery_date=delivery_date,
    )

    db.session.add(item)
    db.session.commit()

    return jsonify(item.to_dict()), 201


@laundry_bp.route("", methods=["GET"])
@login_required
def list_laundry_requests():
    items = (
        LaundryRequest.query
        .filter_by(student_id=str(current_user.id))
        .order_by(LaundryRequest.id.desc())
        .all()
    )

    return jsonify([item.to_dict() for item in items]), 200


@laundry_bp.route("/<int:request_id>", methods=["GET"])
@login_required
def get_laundry_request(request_id):
    item, failure = owned_request(request_id)

    if failure:
        return failure

    return jsonify(item.to_dict()), 200


@laundry_bp.route("/<int:request_id>", methods=["PATCH"])
@login_required
def update_laundry_request(request_id):
    item, failure = owned_request(request_id)

    if failure:
        return failure

    data = request.get_json(silent=True)

    if not isinstance(data, dict) or not data:
        return error("A non-empty JSON object is required", 400)

    # Students may cancel their own pending requests only.
    if set(data) != {"status"} or data["status"] != "cancelled":
        return error("Only cancellation of a pending request is allowed", 403)

    if item.status != "pending":
        return error("Only pending requests can be cancelled", 409)

    item.status = "cancelled"
    db.session.commit()

    return jsonify(item.to_dict()), 200
