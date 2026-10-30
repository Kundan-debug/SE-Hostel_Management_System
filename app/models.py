
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


COMPLAINT_CATEGORIES = (
    "Room Maintenance",
    "Electrical",
    "Plumbing",
    "Cleanliness",
    "Internet / Wi-Fi",
    "Security",
    "Other",
)
COMPLAINT_PRIORITIES = ("Low", "Medium", "High")
COMPLAINT_STATUSES = ("Open", "In Progress", "Resolved")


def _sql_list(values):
    return ", ".join(f"'{value}'" for value in values)


class Complaint(db.Model):
    __tablename__ = "complaints"
    __table_args__ = (
        CheckConstraint(
            f"category IN ({_sql_list(COMPLAINT_CATEGORIES)})",
            name="ck_complaint_category",
        ),
        CheckConstraint(
            f"priority IN ({_sql_list(COMPLAINT_PRIORITIES)})",
            name="ck_complaint_priority",
        ),
        CheckConstraint(
            f"status IN ({_sql_list(COMPLAINT_STATUSES)})",
            name="ck_complaint_status",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id"),
        nullable=False,
        index=True,
    )
    category = db.Column(db.String(30), nullable=False)
    description = db.Column(db.String(1000), nullable=False)
    priority = db.Column(db.String(10), nullable=False, default="Medium")
    status = db.Column(
        db.String(20),
        nullable=False,
        default="Open",
        index=True,
    )
    attachment_filename = db.Column(db.String(255), nullable=True)
    attachment_name = db.Column(db.String(255), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    student = db.relationship("Student", backref="complaints")


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


class MessMenu(db.Model):
    __tablename__ = "mess_menu"
    __table_args__ = (
        db.UniqueConstraint(
            "day_of_week",
            "meal_type",
            name="uq_mess_menu_day_meal",
        ),
        CheckConstraint(
            "meal_type IN ('Breakfast', 'Lunch', 'Snacks', 'Dinner')",
            name="ck_mess_menu_meal_type",
        ),
        CheckConstraint(
            "end_time > start_time",
            name="ck_mess_menu_time",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    day_of_week = db.Column(db.String(10), nullable=False)
    meal_type = db.Column(db.String(20), nullable=False)
    menu_items = db.Column(db.Text, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    is_available = db.Column(db.Boolean, nullable=False, default=True)


class MealRegistration(db.Model):
    __tablename__ = "meal_registrations"
    __table_args__ = (
        db.UniqueConstraint(
            "student_id",
            "menu_id",
            name="uq_meal_registration_student_menu",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id"),
        nullable=False,
        index=True,
    )
    menu_id = db.Column(
        db.Integer,
        db.ForeignKey("mess_menu.id"),
        nullable=False,
        index=True,
    )
    registered_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    student = db.relationship("Student", backref="meal_registrations")
    menu = db.relationship("MessMenu", backref="registrations")


class MessAttendance(db.Model):
    __tablename__ = "mess_attendance"
    __table_args__ = (
        db.UniqueConstraint(
            "student_id",
            "attendance_date",
            "meal_type",
            name="uq_mess_attendance_student_meal_date",
        ),
        CheckConstraint(
            "meal_type IN ('Breakfast', 'Lunch', 'Snacks', 'Dinner')",
            name="ck_mess_attendance_meal_type",
        ),
        CheckConstraint(
            "status IN ('Present', 'Absent')",
            name="ck_mess_attendance_status",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id"),
        nullable=False,
        index=True,
    )
    attendance_date = db.Column(db.Date, nullable=False, index=True)
    meal_type = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(10), nullable=False)

    student = db.relationship("Student", backref="mess_attendance")


class MessFeedback(db.Model):
    __tablename__ = "mess_feedback"
    __table_args__ = (
        CheckConstraint(
            "category IN ('Feedback', 'Complaint')",
            name="ck_mess_feedback_category",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id"),
        nullable=False,
        index=True,
    )
    category = db.Column(db.String(20), nullable=False)
    message = db.Column(db.String(1000), nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    student = db.relationship("Student", backref="mess_feedback")


class MessHoliday(db.Model):
    __tablename__ = "mess_holidays"

    id = db.Column(db.Integer, primary_key=True)
    holiday_date = db.Column(db.Date, unique=True, nullable=False, index=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.String(500), nullable=True)


class MessFee(db.Model):
    __tablename__ = "mess_fees"
    __table_args__ = (
        db.UniqueConstraint(
            "student_id",
            "billing_month",
            name="uq_mess_fee_student_month",
        ),
        CheckConstraint(
            "amount >= 0",
            name="ck_mess_fee_amount_nonnegative",
        ),
        CheckConstraint(
            "status IN ('Due', 'Paid')",
            name="ck_mess_fee_status",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id"),
        nullable=False,
        index=True,
    )
    billing_month = db.Column(db.String(7), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(10), nullable=False, default="Due")

    student = db.relationship("Student", backref="mess_fees")


class Warden(UserMixin, db.Model):
    """A separate authentication identity for hostel wardens."""
    __tablename__ = "wardens"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)

    @property
    def is_warden(self):
        return True

    def get_id(self):
        return f"warden:{self.id}"


class LostFoundItem(db.Model):
    __tablename__ = "lost_found_items"
    __table_args__ = (
        CheckConstraint("item_type IN ('Lost', 'Found')", name="ck_lost_found_item_type"),
        CheckConstraint("status IN ('Open', 'Claimed', 'Returned')", name="ck_lost_found_status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id"),
        nullable=False,
        index=True,
    )
    item_type = db.Column(db.String(10), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(1000), nullable=False)
    location = db.Column(db.String(150), nullable=False)
    item_date = db.Column(db.Date, nullable=False)
    photo_filename = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="Open")
    claimant_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id"),
        nullable=True,
    )
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    reporter = db.relationship(
        "Student",
        foreign_keys=[student_id],
        backref="reported_lost_found_items",
    )
    claimant = db.relationship(
        "Student",
        foreign_keys=[claimant_id],
    )
