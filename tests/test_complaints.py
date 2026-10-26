from io import BytesIO
from pathlib import Path

import pytest

from app import db
from app.models import Complaint, Student
from conftest import log_in, make_student

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 64
VALID_FORM = {
    "category": "Room Maintenance",
    "priority": "High",
    "description": "The ceiling fan in my room is not working.",
}


def submit(client, **overrides):
    data = {**VALID_FORM, **overrides}
    data = {key: value for key, value in data.items() if value is not None}
    return client.post(
        "/complaints/",
        data=data,
        content_type="multipart/form-data",
    )


def student_id():
    return Student.query.filter_by(email="student@gmail.com").one().id


# Access control


def test_complaints_page_requires_login(client):
    response = client.get("/complaints/")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_submit_requires_login(client):
    response = submit(client)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    assert Complaint.query.count() == 0


def test_home_links_to_complaints(logged_in_client):
    response = logged_in_client.get("/")

    assert response.status_code == 200
    assert b"Complaints" in response.data
    assert b"/complaints/" in response.data


# Viewing


def test_complaints_page_loads(logged_in_client):
    response = logged_in_client.get("/complaints/")

    assert response.status_code == 200
    assert b"Submit a Complaint" in response.data
    assert b"You have not submitted any complaints yet." in response.data


# Submitting


def test_submit_complaint_success(logged_in_client):
    response = submit(logged_in_client)

    assert response.status_code == 302
    complaint = Complaint.query.one()
    assert complaint.student_id == student_id()
    assert complaint.category == "Room Maintenance"
    assert complaint.priority == "High"
    assert complaint.status == "Open"
    assert complaint.attachment_filename is None


def test_submitted_complaint_is_visible_with_status(logged_in_client):
    submit(logged_in_client)

    response = logged_in_client.get("/complaints/")

    assert b"The ceiling fan in my room is not working." in response.data
    assert b"Open" in response.data
    assert b"High" in response.data


def test_success_message_after_redirect(logged_in_client):
    response = logged_in_client.post(
        "/complaints/",
        data=VALID_FORM,
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert b"Complaint submitted successfully." in response.data


def test_description_is_trimmed(logged_in_client):
    submit(logged_in_client, description="   Leaking tap in bathroom   ")

    assert Complaint.query.one().description == "Leaking tap in bathroom"


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"category": ""}, b"valid complaint category"),
        ({"category": "Not A Category"}, b"valid complaint category"),
        ({"category": None}, b"valid complaint category"),
        ({"priority": ""}, b"valid priority"),
        ({"priority": "Urgent"}, b"valid priority"),
        ({"description": ""}, b"describe your complaint"),
        ({"description": "   "}, b"describe your complaint"),
        ({"description": "too short"}, b"at least 10 characters"),
        ({"description": "x" * 1001}, b"at most 1000 characters"),
    ],
)
def test_invalid_submissions_are_rejected(
    logged_in_client, overrides, message
):
    response = submit(logged_in_client, **overrides)

    assert response.status_code == 400
    assert message in response.data
    assert Complaint.query.count() == 0


def test_rejected_form_keeps_entered_values(logged_in_client):
    response = submit(
        logged_in_client,
        description="Wi-Fi keeps dropping every evening",
        priority="",
    )

    assert response.status_code == 400
    assert b"Wi-Fi keeps dropping every evening" in response.data


@pytest.mark.parametrize("category", [
    "Room Maintenance", "Electrical", "Plumbing", "Cleanliness",
    "Internet / Wi-Fi", "Security", "Other",
])
@pytest.mark.parametrize("priority", ["Low", "Medium", "High"])
def test_every_category_and_priority_is_accepted(
    logged_in_client, category, priority
):
    response = submit(logged_in_client, category=category,
                      priority=priority)

    assert response.status_code == 302
    assert Complaint.query.count() == 1


# Attachments


def test_submit_with_valid_attachment(logged_in_client, app):
    response = logged_in_client.post(
        "/complaints/",
        data={**VALID_FORM,
              "attachment": (BytesIO(PNG_BYTES), "fan photo.png")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 302
    complaint = Complaint.query.one()
    assert complaint.attachment_name == "fan_photo.png"
    assert complaint.attachment_filename.endswith(".png")
    assert complaint.attachment_filename != "fan_photo.png"

    saved = list((Path(app.config["UPLOAD_FOLDER"]) / "complaints").iterdir())
    assert [file.name for file in saved] == [complaint.attachment_filename]


def test_owner_can_download_attachment(logged_in_client):
    logged_in_client.post(
        "/complaints/",
        data={**VALID_FORM,
              "attachment": (BytesIO(PNG_BYTES), "proof.png")},
        content_type="multipart/form-data",
    )
    complaint = Complaint.query.one()

    response = logged_in_client.get(
        f"/complaints/{complaint.id}/attachment"
    )

    assert response.status_code == 200
    assert response.data == PNG_BYTES
    assert "attachment" in response.headers["Content-Disposition"]


def test_other_student_cannot_download_attachment(app, client):
    log_in(client)
    client.post(
        "/complaints/",
        data={**VALID_FORM,
              "attachment": (BytesIO(PNG_BYTES), "proof.png")},
        content_type="multipart/form-data",
    )
    complaint_id = Complaint.query.one().id
    client.post("/logout")

    db.session.add(make_student("other@gmail.com", "OTHER456",
                                room="202"))
    db.session.commit()
    log_in(client, "other@gmail.com")

    response = client.get(f"/complaints/{complaint_id}/attachment")

    assert response.status_code == 404


def test_attachment_download_requires_login(client):
    response = client.get("/complaints/1/attachment")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_download_for_complaint_without_attachment_redirects(
    logged_in_client
):
    submit(logged_in_client)
    complaint = Complaint.query.one()

    response = logged_in_client.get(
        f"/complaints/{complaint.id}/attachment"
    )

    assert response.status_code == 302


@pytest.mark.parametrize("filename", ["virus.exe", "notes.txt",
                                      "archive.zip", "noextension"])
def test_disallowed_attachment_types_are_rejected(
    logged_in_client, filename
):
    response = logged_in_client.post(
        "/complaints/",
        data={**VALID_FORM,
              "attachment": (BytesIO(b"data"), filename)},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert b"Attach a PDF, JPG, JPEG, or PNG file." in response.data
    assert Complaint.query.count() == 0


def test_oversized_attachment_is_rejected(logged_in_client, app):
    app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024
    big = BytesIO(b"0" * (5 * 1024 * 1024 + 1))

    response = logged_in_client.post(
        "/complaints/",
        data={**VALID_FORM, "attachment": (big, "big.pdf")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert b"5 MB or smaller" in response.data
    assert Complaint.query.count() == 0


def test_failed_save_removes_uploaded_file(logged_in_client, app,
                                           monkeypatch):
    def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(db.session, "commit", boom)

    response = logged_in_client.post(
        "/complaints/",
        data={**VALID_FORM,
              "attachment": (BytesIO(PNG_BYTES), "proof.png")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 500
    assert b"could not be submitted" in response.data
    folder = Path(app.config["UPLOAD_FOLDER"]) / "complaints"
    assert list(folder.iterdir()) == []


# Tracking


def test_status_changes_are_reflected(logged_in_client):
    submit(logged_in_client)
    complaint = Complaint.query.one()

    complaint.status = "In Progress"
    db.session.commit()
    assert b"In Progress" in logged_in_client.get("/complaints/").data

    complaint.status = "Resolved"
    db.session.commit()
    assert b"Resolved" in logged_in_client.get("/complaints/").data


def test_status_filter(logged_in_client):
    submit(logged_in_client, description="Open complaint about a fan")
    submit(logged_in_client, description="Resolved complaint about a tap")
    resolved = Complaint.query.filter(
        Complaint.description.like("Resolved%")
    ).one()
    resolved.status = "Resolved"
    db.session.commit()

    response = logged_in_client.get("/complaints/?status=Resolved")

    assert b"Resolved complaint about a tap" in response.data
    assert b"Open complaint about a fan" not in response.data


def test_empty_filter_result_message(logged_in_client):
    submit(logged_in_client)

    response = logged_in_client.get("/complaints/?status=Resolved")

    assert b'No complaints with status "Resolved".' in response.data


def test_unknown_status_filter_is_ignored(logged_in_client):
    submit(logged_in_client)

    response = logged_in_client.get("/complaints/?status=Bogus")

    assert response.status_code == 200
    assert b"The ceiling fan in my room is not working." in response.data


def test_newest_complaint_is_listed_first(logged_in_client):
    submit(logged_in_client, description="First complaint submitted")
    submit(logged_in_client, description="Second complaint submitted")

    body = logged_in_client.get("/complaints/").data

    assert body.index(b"Second complaint") < body.index(b"First complaint")


def test_students_only_see_their_own_complaints(app, client):
    log_in(client)
    submit(client, description="My own private complaint")
    client.post("/logout")

    db.session.add(make_student("other@gmail.com", "OTHER456",
                                room="202"))
    db.session.commit()
    log_in(client, "other@gmail.com")

    response = client.get("/complaints/")

    assert b"My own private complaint" not in response.data
    assert b"You have not submitted any complaints yet." in response.data


# Database constraints


@pytest.mark.parametrize("field, value", [
    ("category", "Bogus"),
    ("priority", "Urgent"),
    ("status", "Closed"),
])
def test_database_rejects_invalid_enum_values(app, field, value):
    from sqlalchemy.exc import IntegrityError

    values = {
        "student_id": student_id(),
        "category": "Other",
        "description": "Valid description text",
        "priority": "Low",
        "status": "Open",
        field: value,
    }
    db.session.add(Complaint(**values))

    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
