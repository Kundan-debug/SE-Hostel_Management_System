
from datetime import datetime, timezone

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
        db.Integer,
        db.ForeignKey("students.id"),
        nullable=False,
        index=True,
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
        db.Integer,
        db.ForeignKey("fees.id"),
        nullable=False,
        index=True,
    )
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id"),
        nullable=False,
        index=True,
    )
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_date = db.Column(
        db.DateTime,
        nullable=False,
        default=db.func.now(),
    )
    payment_method = db.Column(
        db.String(50),
        nullable=False,
        default="Demo payment",
    )
    transaction_reference = db.Column(
        db.String(100),
        unique=True,
        nullable=False,
    )
    status = db.Column(
        db.String(20),
        nullable=False,
        default="Pending",
    )

    fee = db.relationship("Fee", back_populates="payments")
    student = db.relationship("Student", backref="payments")


class LaundryRequest(db.Model):
    __tablename__ = "laundry_requests"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), nullable=False, index=True)
    item_details = db.Column(db.String(500), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    pickup_date = db.Column(db.Date, nullable=False)
    delivery_date = db.Column(db.Date, nullable=True)
    status = db.Column(
        db.String(20),
        nullable=False,
        default="pending",
        index=True,
    )
    charges = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    payment_status = db.Column(
        db.String(20),
        nullable=False,
        default="unpaid",
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
                self.delivery_date.isoformat()
                if self.delivery_date
                else None
            ),
            "status": self.status,
            "charges": float(self.charges),
            "payment_status": self.payment_status,
            "created_at": self.created_at.isoformat(),
        }


class LeaveApplication(db.Model):
    __tablename__ = "leave_applications"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id"),
        nullable=False,
        index=True,
    )
    leave_type = db.Column(db.String(30), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.String(1000), nullable=False)
    status = db.Column(
        db.String(20),
        nullable=False,
        default="Pending",
        index=True,
    )
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    student = db.relationship("Student", backref="leave_applications")


class Room(db.Model):
    __tablename__ = "rooms"
    __table_args__ = (
        db.UniqueConstraint(
            "hostel_name",
            "room_number",
            name="uq_room_hostel_number",
        ),
        CheckConstraint(
            "capacity > 0",
            name="ck_room_capacity_positive",
        ),
        CheckConstraint(
            "occupied_beds >= 0 AND occupied_beds <= capacity",
            name="ck_room_occupancy",
        ),
        CheckConstraint(
            "maintenance_status IN ('Available', 'Under Maintenance')",
            name="ck_room_maintenance_status",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    hostel_name = db.Column(db.String(100), nullable=False)
    room_number = db.Column(db.String(20), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    occupied_beds = db.Column(db.Integer, nullable=False, default=0)
    maintenance_status = db.Column(
        db.String(30),
        nullable=False,
        default="Available",
    )

    @property
    def available_beds(self):
        return self.capacity - self.occupied_beds


class CommonFacility(db.Model):
    __tablename__ = "common_facilities"
    __table_args__ = (
        CheckConstraint(
            "capacity > 0",
            name="ck_facility_capacity_positive",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(500), nullable=True)
    location = db.Column(db.String(150), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    is_available = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
    )

    bookings = db.relationship(
        "FacilityBooking",
        back_populates="facility",
        cascade="all, delete-orphan",
    )


class FacilityBooking(db.Model):
    __tablename__ = "facility_bookings"
    __table_args__ = (
        CheckConstraint(
            "end_time > start_time",
            name="ck_booking_end_after_start",
        ),
        CheckConstraint(
            "status IN ('Pending', 'Confirmed', 'Cancelled')",
            name="ck_facility_booking_status",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id"),
        nullable=False,
        index=True,
    )
    facility_id = db.Column(
        db.Integer,
        db.ForeignKey("common_facilities.id"),
        nullable=False,
        index=True,
    )
    booking_date = db.Column(db.Date, nullable=False, index=True)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    status = db.Column(
        db.String(20),
        nullable=False,
        default="Pending",
        index=True,
    )
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    student = db.relationship("Student", backref="facility_bookings")
    facility = db.relationship(
        "CommonFacility",
        back_populates="bookings",
    )

class Announcement(db.Model):
    __tablename__ = "announcements"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    category = db.Column(
        db.String(30),
        nullable=False,
        default="General",
    )
    published_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
