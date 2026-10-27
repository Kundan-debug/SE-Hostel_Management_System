from werkzeug.security import generate_password_hash
from app import db
from app.models import Student, Warden

def log_in_warden(client):
    w = Warden(full_name="Test Warden", email="warden-profiles@example.com",
               password_hash=generate_password_hash("WardenPass123!"))
    db.session.add(w)
    db.session.commit()
    client.post("/login", data={"email": w.email, "password": "WardenPass123!"})

def test_student_cannot_access_student_directory(logged_in_client):
    assert logged_in_client.get("/warden/students/").status_code == 403

def test_anonymous_user_redirected_from_student_directory(client):
    r=client.get("/warden/students/")
    assert r.status_code == 302 and "/login" in r.headers["Location"]

def test_warden_can_search_and_view_students(app, client):
    log_in_warden(client)
    r=client.get("/warden/students/?q=TEST123")
    assert r.status_code == 200 and b"Test Student" in r.data
    r=client.get("/warden/students/1")
    assert r.status_code == 200 and b"Parent" in r.data

def test_student_search_returns_no_unrelated_records(app, client):
    log_in_warden(client)
    r=client.get("/warden/students/?q=not-a-real-student")
    assert r.status_code == 200 and b"No students found" in r.data

def test_missing_student_profile_returns_404(client):
    # A logged-in warden is required before the detail route can be tested.
    log_in_warden(client)
    assert client.get("/warden/students/99999").status_code == 404
