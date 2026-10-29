import os
import re
from pathlib import Path
from urllib.parse import quote_plus
from uuid import uuid4

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
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.exc import IntegrityError
from werkzeug.security import (
    generate_password_hash,
    check_password_hash,
)
from werkzeug.utils import secure_filename

load_dotenv()

db = SQLAlchemy()

csrf = CSRFProtect()

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access this page."

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}
MAX_FILE_SIZE = 5 * 1024 * 1024


def create_app(test_config=None):
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

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
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = (
        os.getenv("COOKIE_SECURE", "false").lower() == "true"
    )

    if test_config:
        app.config.update(test_config)
    if not app.config.get("SECRET_KEY") and not app.config.get("TESTING"):
        raise RuntimeError("SECRET_KEY must be set in the environment.")

    upload_folder = Path(app.root_path) / "static" / "uploads"
    upload_folder.mkdir(parents=True, exist_ok=True)
    app.config["UPLOAD_FOLDER"] = str(upload_folder)


    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.models import (
        Student,
        Fee,
        Payment,
        LeaveApplication,
        Room,
        Complaint,
        CommonFacility,
        FacilityBooking,
        Announcement,
        MessMenu,
        MealRegistration,
        MessAttendance,
        MessFeedback,
        MessHoliday,
        MessFee,
        Warden,
    )

    @login_manager.user_loader
    def load_user(user_id):
        if not user_id:
            return None
        if user_id.startswith("warden:"):
            try:
                return db.session.get(Warden, int(user_id.split(":", 1)[1]))
            except (TypeError, ValueError):
                return None
        if user_id.startswith("student:"):
            user_id = user_id.split(":", 1)[1]
        try:
            return db.session.get(Student, int(user_id))
        except (TypeError, ValueError):
            return None

    if not app.config.get("TESTING"):
        with app.app_context():
            db.create_all()

    from app.laundry_routes import laundry_bp
    app.register_blueprint(laundry_bp)

    from app.student_directory_routes import student_directory_bp
    app.register_blueprint(student_directory_bp)

    from app.lost_found_routes import lost_found_bp
    app.register_blueprint(lost_found_bp)

    @app.route("/")
    @login_required
    def home():
        return render_template("home.html")

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

        for field, value in data.items():
            if not value:
                errors[field] = "This field is required."

        name_pattern = r"[A-Za-z]+(?:[ '-][A-Za-z]+)*"

        for field in ("full_name", "parent_name"):
            if field not in errors and not re.fullmatch(
                name_pattern, data[field]
            ):
                errors[field] = (
                    "Use letters only, with spaces, apostrophes, "
                    "or hyphens between names."
                )

        if "email" not in errors:
            if not re.fullmatch(
                r"[A-Za-z0-9._%+-]+@gmail\.com",
                data["email"],
                re.IGNORECASE,
            ):
                errors["email"] = (
                    "Enter a valid Gmail address ending in @gmail.com."
                )

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

        for field in ("contact_number", "parent_contact_number"):
            if field not in errors and not re.fullmatch(
                r"[0-9]{10}", data[field]
            ):
                errors[field] = "Enter exactly 10 digits."

        if "srn" not in errors and not re.fullmatch(
            r"[A-Za-z0-9]+", data["srn"]
        ):
            errors["srn"] = (
                "SRN must contain letters and numbers only."
            )

        if "room_number" not in errors and not re.fullmatch(
            r"[A-Za-z0-9-]+", data["room_number"]
        ):
            errors["room_number"] = (
                "Use letters, numbers, and hyphens only."
            )

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
            if getattr(current_user, "is_warden", False):
                return redirect(url_for("warden.dashboard"))
            return redirect(url_for("room.room_details"))

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

        warden = Warden.query.filter_by(email=email).first()
        if warden is not None:
            if not check_password_hash(warden.password_hash, password):
                return render_template(
                    "login.html",
                    error="Invalid email or password.",
                    email=email,
                ), 401
            login_user(warden)
            flash("Login successful!", "success")
            return redirect(url_for("warden.dashboard"))

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

        next_page = request.args.get("next", "")

        if next_page.startswith("/") and not next_page.startswith("//"):
            return redirect(next_page)

        return redirect(url_for("room.room_details"))

    @app.route("/logout", methods=["POST"])
    @login_required
    def logout():
        logout_user()
        flash("You have been logged out.", "success")
        return redirect(url_for("login"))

    from app.fees import fees_bp
    app.register_blueprint(fees_bp)

    from app.leave_routes import leave_bp
    app.register_blueprint(leave_bp)

    from app.room_routes import room_bp
    app.register_blueprint(room_bp)

    from app.facility_routes import facility_bp
    app.register_blueprint(facility_bp)

    from app.complaint_routes import complaint_bp
    app.register_blueprint(complaint_bp)

    from app.profile_routes import profile_bp
    app.register_blueprint(profile_bp)

    from app.announcement_routes import announcement_bp
    app.register_blueprint(announcement_bp)

    from app.mess_routes import mess_bp
    app.register_blueprint(mess_bp)

    from app.warden_routes import warden_bp
    app.register_blueprint(warden_bp)

    return app
