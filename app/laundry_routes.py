
from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from app import db
from app.models import LaundryRequest

laundry_bp = Blueprint("laundry", __name__, url_prefix="/api/laundry")

VALID_STATUSES = {
    "pending", "processing", "ready", "delivered", "cancelled"
}


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


def student_requests():
    """Return requests belonging only to the logged-in student."""
    return LaundryRequest.query.filter_by(
        student_id=current_user.srn
    )


@laundry_bp.get("/")
@login_required
def laundry_page():
    return render_template("laundry.html")


@laundry_bp.route("", methods=["GET", "POST"])
@login_required
def laundry_collection():
    if request.method == "GET":
        items = student_requests().order_by(
            LaundryRequest.id.desc()
        ).all()
        return jsonify([item.to_dict() for item in items]), 200

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "A JSON object is required"}), 400

    item_details = data.get("item_details")
    quantity = data.get("quantity")

    if not isinstance(item_details, str) or not item_details.strip():
        return jsonify({"error": "Item details are required"}), 400

    item_details = item_details.strip()

    if len(item_details) > 500:
        return jsonify({"error": "Item details must be 500 characters or fewer"}), 400

    if type(quantity) is not int or not 1 <= quantity <= 100:
        return jsonify({"error": "Quantity must be between 1 and 100"}), 400

    try:
        pickup_date = parse_date(data.get("pickup_date"), "pickup_date", True)
        delivery_date = parse_date(data.get("delivery_date"), "delivery_date")

        if pickup_date < date.today():
            return jsonify({"error": "Pickup date cannot be in the past"}), 400

        if delivery_date and delivery_date < pickup_date:
            return jsonify({
                "error": "Delivery date cannot be before pickup date"
            }), 400

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    # Students cannot choose their own charges, status, or payment status.
    laundry_request = LaundryRequest(
        student_id=current_user.srn,
        item_details=item_details,
        quantity=quantity,
        pickup_date=pickup_date,
        delivery_date=delivery_date,
        status="pending",
        charges=Decimal("0.00"),
        payment_status="unpaid",
    )

    db.session.add(laundry_request)
    db.session.commit()

    return jsonify(laundry_request.to_dict()), 201


@laundry_bp.get("/<int:request_id>")
@login_required
def get_laundry_request(request_id):
    item = student_requests().filter_by(id=request_id).first()

    if item is None:
        return jsonify({"error": "Laundry request not found"}), 404

    return jsonify(item.to_dict()), 200


@laundry_bp.patch("/<int:request_id>")
@login_required
def update_laundry_request(request_id):
    item = student_requests().filter_by(id=request_id).first()

    if item is None:
        return jsonify({"error": "Laundry request not found"}), 404

    data = request.get_json(silent=True)

    if not isinstance(data, dict) or not data:
        return jsonify({"error": "A non-empty JSON object is required"}), 400

    # Students may cancel their own pending request only.
    if set(data) != {"status"} or data.get("status") != "cancelled":
        return jsonify({
            "error": "Students may only cancel their own pending requests"
        }), 403

    if item.status != "pending":
        return jsonify({
            "error": "Only pending requests can be cancelled"
        }), 400

    item.status = "cancelled"
    db.session.commit()

    return jsonify(item.to_dict()), 200
