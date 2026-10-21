
from flask_login import UserMixin
from sqlalchemy import CheckConstraint

from app import db


class Student(UserMixin, db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    contact_number = db.Column(db.String(10), nullable=False)
    srn = db.Column(db.String(30), unique=True, nullable=False)
    parent_name = db.Column(db.String(100), nullable=False)
    parent_contact_number = db.Column(db.String(10), nullable=False)
    hostel_name = db.Column(db.String(100), nullable=False)
    room_number = db.Column(db.String(20), nullable=False)
    id_proof_filename = db.Column(db.String(255), nullable=False)


class Fee(db.Model):
    __tablename__ = "fees"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_fee_amount_positive"),
        CheckConstraint(
            "status IN ('Due', 'Paid')",
            name="ck_fee_status",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer, db.ForeignKey("students.id"), nullable=False, index=True
    )
    description = db.Column(db.String(200), nullable=False)
    fee_type = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Due")

    student = db.relationship("Student", backref="fees")
    payments = db.relationship("Payment", back_populates="fee")


class Payment(db.Model):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payment_amount_positive"),
        CheckConstraint(
            "status IN ('Pending', 'Success', 'Failed')",
            name="ck_payment_status",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    fee_id = db.Column(
        db.Integer, db.ForeignKey("fees.id"), nullable=False, index=True
    )
    student_id = db.Column(
        db.Integer, db.ForeignKey("students.id"), nullable=False, index=True
    )
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_date = db.Column(
        db.DateTime, nullable=False, default=db.func.now()
    )
    payment_method = db.Column(
        db.String(50), nullable=False, default="Demo payment"
    )
    transaction_reference = db.Column(
        db.String(100), unique=True, nullable=False
    )
    status = db.Column(
        db.String(20), nullable=False, default="Pending"
    )

    fee = db.relationship("Fee", back_populates="payments")
    student = db.relationship("Student", backref="payments")
from datetime import datetime, timezone


class LaundryRequest(db.Model):
    __tablename__ = "laundry_requests"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), nullable=False, index=True)
    item_details = db.Column(db.String(500), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    pickup_date = db.Column(db.Date, nullable=False)
    delivery_date = db.Column(db.Date, nullable=True)
    status = db.Column(
        db.String(20), nullable=False, default="pending", index=True
    )
    charges = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    payment_status = db.Column(
        db.String(20), nullable=False, default="unpaid"
    )
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "student_id": self.student_id,
            "item_details": self.item_details,
            "quantity": self.quantity,
            "pickup_date": self.pickup_date.isoformat(),
            "delivery_date": (
                self.delivery_date.isoformat() if self.delivery_date else
None
            ),
            "status": self.status,
            "charges": float(self.charges),
            "payment_status": self.payment_status,
            "created_at": self.created_at.isoformat(),
        }
