
from decimal import Decimal
from uuid import uuid4

from flask import (
    Blueprint, abort, current_app, flash, redirect, render_template,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import select

from app import db
from app.models import Fee, Payment

fees_bp = Blueprint("fees", __name__)


@fees_bp.get("/fees")
@login_required
def manage_fees():
    fees = db.session.scalars(
        select(Fee)
        .where(Fee.student_id == current_user.id)
        .order_by(Fee.due_date.asc())
    ).all()

    payments = db.session.scalars(
        select(Payment)
        .where(Payment.student_id == current_user.id)
        .order_by(Payment.payment_date.desc())
    ).all()

    total_due = sum(
        (fee.amount for fee in fees if fee.status == "Due"),
        Decimal("0.00"),
    )

    return render_template(
        "fees.html",
        fees=fees,
        payments=payments,
        total_due=total_due,
    )


@fees_bp.post("/fees/<int:fee_id>/pay")
@login_required
def simulate_payment(fee_id):
    fee = db.session.scalar(
        select(Fee).where(
            Fee.id == fee_id,
            Fee.student_id == current_user.id,
        )
    )

    if fee is None:
        abort(404)

    if fee.status != "Due":
        flash("This fee has already been paid.", "error")
        return redirect(url_for("fees.manage_fees"))

    # DEMO ONLY: no real money is transferred.
    payment = Payment(
        fee_id=fee.id,
        student_id=current_user.id,
        amount=fee.amount,
        payment_method="Simulated payment",
        transaction_reference=f"DEMO-{uuid4().hex[:16].upper()}",
        status="Success",
    )

    try:
        fee.status = "Paid"
        db.session.add(payment)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Simulated payment failed")
        flash("Payment could not be recorded. Please try again.", "error")
        return redirect(url_for("fees.manage_fees"))

    flash("Demo payment recorded successfully. No real money was charged.", "success")
    return redirect(url_for("fees.receipt", payment_id=payment.id))


@fees_bp.get("/payments/<int:payment_id>/receipt")
@login_required
def receipt(payment_id):
    payment = db.session.scalar(
        select(Payment).where(
            Payment.id == payment_id,
            Payment.student_id == current_user.id,
            Payment.status == "Success",
        )
    )

    if payment is None:
        abort(404)

    return render_template("receipt.html", payment=payment)
