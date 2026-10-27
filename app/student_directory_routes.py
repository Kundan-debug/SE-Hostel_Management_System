"""Warden-only student directory and profile detail views."""
from flask import Blueprint, abort, render_template, request
from sqlalchemy import or_
from app import db
from app.models import Student
from app.warden_routes import warden_required

student_directory_bp = Blueprint("student_directory", __name__, url_prefix="/warden/students")

@student_directory_bp.route("/")
@warden_required
def list_students():
    query = request.args.get("q", "").strip()
    students_query = Student.query
    if query:
        pattern = f"%{query}%"
        students_query = students_query.filter(or_(
            Student.full_name.ilike(pattern),
            Student.email.ilike(pattern),
            Student.srn.ilike(pattern),
        ))
    students = students_query.order_by(Student.full_name.asc()).all()
    return render_template("warden_students.html", students=students, query=query)

@student_directory_bp.route("/<int:student_id>")
@warden_required
def student_detail(student_id):
    student = db.session.get(Student, student_id)
    if student is None:
        abort(404)
    return render_template("warden_student_detail.html", student=student)
