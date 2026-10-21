
from datetime import datetime, timezone

from app import db


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
                self.delivery_date.isoformat() if self.delivery_date else None
            ),
            "status": self.status,
            "charges": float(self.charges),
            "payment_status": self.payment_status,
            "created_at": self.created_at.isoformat(),
        }
