
from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request

from app import db
from app.laundry.models import LaundryRequest

laundry_bp = Blueprint("laundry", __name__, url_prefix="/api/laundry")

VALID_STATUSES = {"pending", "processing", "ready", "delivered", "cancelled"}
VALID_PAYMENT_STATUSES = {"unpaid", "paid"}


def parse_date(value, field_name, required=False):
    if value is None or value == "":
        if required:
            raise ValueError(f"{field_name} is required")
        return None

    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must use YYYY-MM-DD format")


@laundry_bp.route("", methods=["POST"])
def create_laundry_request():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "A JSON object is required"}), 400

    student_id = data.get("student_id")
    item_details = data.get("item_details")

    if not isinstance(student_id, str) or not student_id.strip():
        return jsonify({"error": "student_id is required"}), 400

    if not isinstance(item_details, str) or not item_details.strip():
        return jsonify({"error": "item_details is required"}), 400

    if len(student_id.strip()) > 50 or len(item_details.strip()) > 500:
        return jsonify({"error": "A field exceeds its maximum length"}), 400

    quantity = data.get("quantity")
    if type(quantity) is not int or quantity < 1:
        return jsonify({"error": "quantity must be a positive integer"}), 400

    try:
        pickup_date = parse_date(data.get("pickup_date"), "pickup_date", True)
        delivery_date = parse_date(data.get("delivery_date"), "delivery_date")

        if delivery_date and delivery_date < pickup_date:
            return jsonify({
                "error": "delivery_date cannot be before pickup_date"
            }), 400

        charges = Decimal(str(data.get("charges", 0)))

        if (
            not charges.is_finite()
            or charges < 0
            or charges > Decimal("99999999.99")
            or charges.as_tuple().exponent < -2
        ):
            raise ValueError("Invalid charges")

    except (ValueError, InvalidOperation):
        return jsonify({"error": "Invalid date or charges value"}), 400

    laundry_request = LaundryRequest(
        student_id=student_id.strip(),
        item_details=item_details.strip(),
        quantity=quantity,
        pickup_date=pickup_date,
        delivery_date=delivery_date,
        charges=charges,
    )

    db.session.add(laundry_request)
    db.session.commit()

    return jsonify(laundry_request.to_dict()), 201


@laundry_bp.route("", methods=["GET"])
def list_laundry_requests():
    student_id = request.args.get("student_id")
    query = LaundryRequest.query

    if student_id:
        query = query.filter_by(student_id=student_id.strip())

    requests_list = query.order_by(LaundryRequest.id.desc()).all()
    return jsonify([item.to_dict() for item in requests_list]), 200


@laundry_bp.route("/<int:request_id>", methods=["GET"])
def get_laundry_request(request_id):
    laundry_request = db.session.get(LaundryRequest, request_id)

    if laundry_request is None:
        return jsonify({"error": "Laundry request not found"}), 404

    return jsonify(laundry_request.to_dict()), 200


@laundry_bp.route("/<int:request_id>", methods=["PATCH"])
def update_laundry_request(request_id):
    laundry_request = db.session.get(LaundryRequest, request_id)

    if laundry_request is None:
        return jsonify({"error": "Laundry request not found"}), 404

    data = request.get_json(silent=True)

    if not isinstance(data, dict) or not data:
        return jsonify({"error": "A non-empty JSON object is required"}), 400

    allowed_fields = {"status", "payment_status", "charges", "delivery_date"}

    if set(data) - allowed_fields:
        return jsonify({"error": "Unsupported field"}), 400

    if "status" in data:
        if (
            not isinstance(data["status"], str)
            or data["status"] not in VALID_STATUSES
        ):
            return jsonify({"error": "Invalid laundry status"}), 400

        laundry_request.status = data["status"]

    if "payment_status" in data:
        if (
            not isinstance(data["payment_status"], str)
            or data["payment_status"] not in VALID_PAYMENT_STATUSES
        ):
            return jsonify({"error": "Invalid payment status"}), 400

        laundry_request.payment_status = data["payment_status"]

    if "charges" in data:
        try:
            charges = Decimal(str(data["charges"]))

            if (
                not charges.is_finite()
                or charges < 0
                or charges > Decimal("99999999.99")
                or charges.as_tuple().exponent < -2
            ):
                raise ValueError("Invalid charges")

        except (ValueError, InvalidOperation):
            return jsonify({"error": "Invalid charges value"}), 400

        laundry_request.charges = charges

    if "delivery_date" in data:
        try:
            delivery_date = parse_date(data["delivery_date"], "delivery_date")
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        if delivery_date and delivery_date < laundry_request.pickup_date:
            return jsonify({
                "error": "delivery_date cannot be before pickup_date"
            }), 400

        laundry_request.delivery_date = delivery_date

    db.session.commit()

    return jsonify(laundry_request.to_dict()), 200
