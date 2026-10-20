
from app import db


class Student(db.Model):
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
