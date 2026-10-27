import pytest
from werkzeug.security import generate_password_hash
from app import db
from app.models import Announcement, Warden

@pytest.fixture
def logged_in_warden(app, client):
    w = Warden(full_name="Test Warden", email="warden@example.com",
               password_hash=generate_password_hash("WardenPass123!"))
    db.session.add(w); db.session.commit()
    client.post("/login", data={"email": w.email, "password": "WardenPass123!"})
    return client

def test_student_forbidden_from_management(logged_in_client):
    assert logged_in_client.get("/announcements/manage").status_code == 403

def test_anonymous_redirected_from_management(client):
    r = client.get("/announcements/manage")
    assert r.status_code == 302 and "/login" in r.headers["Location"]

def test_warden_can_open_management_page(logged_in_warden):
    assert logged_in_warden.get("/announcements/manage").status_code == 200

def test_warden_can_create_announcement(logged_in_warden):
    r = logged_in_warden.post("/announcements/manage", data={
        "title":"Water shutdown", "message":"Water paused tomorrow.", "category":"Maintenance"})
    assert r.status_code == 302
    assert Announcement.query.one().title == "Water shutdown"

def test_invalid_announcement_rejected(logged_in_warden):
    r = logged_in_warden.post("/announcements/manage", data={"title":"","message":"","category":"General"})
    assert r.status_code == 200 or r.status_code == 400
    assert Announcement.query.count() == 0

def test_warden_can_edit_announcement(logged_in_warden):
    a=Announcement(title="Old",message="Old message",category="General"); db.session.add(a); db.session.commit()
    r=logged_in_warden.post(f"/announcements/{a.id}/edit",data={"title":"New","message":"New message","category":"Event"})
    assert r.status_code == 302 and a.title == "New"

def test_warden_can_delete_announcement(logged_in_warden):
    a=Announcement(title="Delete",message="Message",category="General"); db.session.add(a); db.session.commit()
    r=logged_in_warden.post(f"/announcements/{a.id}/delete")
    assert r.status_code == 302 and Announcement.query.count() == 0

def test_students_can_view_announcements(logged_in_client):
    db.session.add(Announcement(title="Welcome",message="Term starts Monday",category="General")); db.session.commit()
    assert b"Welcome" in logged_in_client.get("/announcements/").data
