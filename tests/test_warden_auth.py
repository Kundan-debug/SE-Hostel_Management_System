import pytest
from werkzeug.security import generate_password_hash
from app import db
from app.models import Warden

@pytest.fixture
def warden(app):
    item = Warden(full_name="Test Warden", email="warden@example.com",
                  password_hash=generate_password_hash("WardenPass123!"))
    db.session.add(item)
    db.session.commit()
    return item

def test_warden_login_redirects_to_dashboard(client, warden):
    r=client.post("/login",data={"email":warden.email,"password":"WardenPass123!"})
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/warden/")

def test_warden_session_persists_across_requests(client, warden):
    client.post("/login",data={"email":warden.email,"password":"WardenPass123!"})
    r=client.get("/warden/")
    assert r.status_code == 200
    assert b"Warden Dashboard" in r.data

def test_student_cannot_access_warden_dashboard(logged_in_client):
    assert logged_in_client.get("/warden/").status_code == 403

def test_unauthenticated_user_cannot_access_warden_dashboard(client):
    r=client.get("/warden/")
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]

def test_warden_wrong_password_rejected(client, warden):
    r=client.post("/login",data={"email":warden.email,"password":"wrong-password"})
    assert r.status_code == 401

def test_warden_table_is_registered_in_metadata(app):
    assert "wardens" in db.metadata.tables
    assert db.metadata.tables["wardens"] is Warden.__table__
