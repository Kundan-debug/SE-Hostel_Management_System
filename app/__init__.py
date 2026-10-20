
import os
import re
from pathlib import Path
from uuid import uuid4
from urllib.parse import quote_plus

from dotenv import load_dotenv
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
)
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from werkzeug.security import (
    generate_password_hash,
    check_password_hash,
)
from werkzeug.utils import secure_filename

load_dotenv()

db = SQLAlchemy()

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access this page."

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}
MAX_FILE_SIZE = 5 * 1024 * 1024


def create_app(test_config=None):
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.getenv(
        "SECRET_KEY", "dev-only-change-me"
    )

    db_user = os.getenv("DB_USER", "root")
    db_password = os.getenv("DB_PASSWORD", "")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "3306")
    db_name = os.getenv("DB_NAME", "hostel_management")

    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"mysql+pymysql://{quote_plus(db_user)}:"
        f"{quote_plus(db_password)}@{db_host}:{db_port}/{db_name}"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE

    if test_config:
        app.config.update(test_config)

    upload_folder = Path(app.root_path) / "static" / "uploads"
    upload_folder.mkdir(parents=True, exist_ok=True)
    app.config["UPLOAD_FOLDER"] = str(upload_folder)

    db.init_app(app)
    login_manager.init_app(app)

    from app.models import Student

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(Student, int(user_id))
        except (TypeError, ValueError):
            return None

    # Create database tables during normal local runs, not tests.
    if not app.config.get("TESTING"):
        with app.app_context():
            db.create_all()

    @app.route("/")
    def home():
        return {
            "message": "Hostel Management System API",
            "status": "running",
        }

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "GET":
            return render_template("register.html")

        field_names = [
            "full_name",
            "email",
            "password",
            "contact_number",
            "srn",
            "parent_name",
            "parent_contact_number",
            "hostel_name",
            "room_number",
        ]

        data = {
            field: request.form.get(field, "").strip()
            for field in field_names
        }
        errors = {}

        # Validate required fields.
        for field, value in data.items():
            if not value:
                errors[field] = "This field is required."

        # Validate student and parent names.
        name_pattern = r"[A-Za-z]+(?:[ '-][A-Za-z]+)*"

        for field in ("full_name", "parent_name"):
            if field not in errors and not re.fullmatch(
                name_pattern, data[field]
            ):
                errors[field] = (
                    "Use letters only, with spaces, apostrophes, "
                    "or hyphens between names."
                )

        # Accept Gmail addresses only.
        if "email" not in errors:
            if not re.fullmatch(
                r"[A-Za-z0-9._%+-]+@gmail\.com",
                data["email"],
                re.IGNORECASE,
            ):
                errors["email"] = (
                    "Enter a valid Gmail address ending in @gmail.com."
                )

        # Validate password strength.
        if "password" not in errors:
            password = data["password"]
            if (
                len(password) < 8
                or not re.search(r"[A-Z]", password)
                or not re.search(r"[a-z]", password)
                or not re.search(r"[0-9]", password)
                or not re.search(r"[^A-Za-z0-9]", password)
            ):
                errors["password"] = (
                    "Use at least 8 characters, including uppercase, "
                    "lowercase, a number, and a special character."
                )

        # Validate contact numbers.
        for field in ("contact_number", "parent_contact_number"):
            if field not in errors and not re.fullmatch(
                r"[0-9]{10}", data[field]
            ):
                errors[field] = "Enter exactly 10 digits."

        # Validate SRN.
        if "srn" not in errors and not re.fullmatch(
            r"[A-Za-z0-9]+", data["srn"]
        ):
            errors["srn"] = (
                "SRN must contain letters and numbers only."
            )

        # Validate room number.
        if "room_number" not in errors and not re.fullmatch(
            r"[A-Za-z0-9-]+", data["room_number"]
        ):
            errors["room_number"] = (
                "Use letters, numbers, and hyphens only."
            )

        # Validate uploaded ID proof.
        id_proof = request.files.get("id_proof")
        original_name = ""

        if not id_proof or not id_proof.filename:
            errors["id_proof"] = "Please upload your ID proof."
        else:
            original_name = secure_filename(id_proof.filename)
            extension = (
                original_name.rsplit(".", 1)[-1].lower()
                if "." in original_name
                else ""
            )

            if extension not in ALLOWED_EXTENSIONS:
                errors["id_proof"] = (
                    "Upload a PDF, JPG, JPEG, or PNG file."
                )
            elif len(id_proof.read()) > MAX_FILE_SIZE:
                errors["id_proof"] = (
                    "The file must be 5 MB or smaller."
                )

            id_proof.seek(0)

        if errors:
            return render_template(
                "register.html",
                errors=errors,
                form_data=data,
            ), 400

        data["email"] = data["email"].lower()
        data["srn"] = data["srn"].upper()

        if Student.query.filter_by(email=data["email"]).first():
            return render_template(
                "register.html",
                errors={"email": "This email is already registered."},
                form_data=data,
            ), 409

        if Student.query.filter_by(srn=data["srn"]).first():
            return render_template(
                "register.html",
                errors={"srn": "This SRN is already registered."},
                form_data=data,
            ), 409

        extension = original_name.rsplit(".", 1)[-1].lower()
        saved_name = f"{uuid4().hex}.{extension}"
        saved_path = Path(app.config["UPLOAD_FOLDER"]) / saved_name

        try:
            id_proof.save(saved_path)

            student = Student(
                full_name=data["full_name"],
                email=data["email"],
                password_hash=generate_password_hash(data["password"]),
                contact_number=data["contact_number"],
                srn=data["srn"],
                parent_name=data["parent_name"],
                parent_contact_number=data["parent_contact_number"],
                hostel_name=data["hostel_name"],
                room_number=data["room_number"],
                id_proof_filename=saved_name,
            )

            db.session.add(student)
            db.session.commit()

        except IntegrityError:
            db.session.rollback()
            saved_path.unlink(missing_ok=True)

            return render_template(
                "register.html",
                errors={
                    "general": (
                        "This email or SRN is already registered."
                    )
                },
                form_data=data,
            ), 409

        except Exception:
            db.session.rollback()
            saved_path.unlink(missing_ok=True)
            app.logger.exception("Student registration failed.")

            return render_template(
                "register.html",
                errors={
                    "general": (
                        "Registration failed. Please try again."
                    )
                },
                form_data=data,
            ), 500

        return render_template(
            "register.html",
            success="Registration completed successfully!",
            form_data={},
        ), 201

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("home"))

        if request.method == "GET":
            return render_template("login.html")

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            return render_template(
                "login.html",
                error="Please enter your email and password.",
                email=email,
            ), 400

        student = Student.query.filter_by(email=email).first()

        if (
            student is None
            or not check_password_hash(student.password_hash, password)
        ):
            return render_template(
                "login.html",
                error="Invalid email or password.",
                email=email,
            ), 401

        login_user(student)
        flash("Login successful!", "success")

        return redirect(url_for("home"))

    @app.route("/logout", methods=["POST"])
    @login_required
    def logout():
        logout_user()
        flash("You have been logged out.", "success")
        return redirect(url_for("login"))

    return app
