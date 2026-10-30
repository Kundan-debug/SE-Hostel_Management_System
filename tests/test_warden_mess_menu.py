from datetime import time

import pytest
from werkzeug.security import generate_password_hash

from app import db
from app.models import MessMenu, Warden


@pytest.fixture
def warden(app):
    item = Warden(
        full_name="Test Warden",
        email="warden@example.com",
        password_hash=generate_password_hash("WardenPass123!"),
    )
    db.session.add(item)
    db.session.commit()
    return item


def _login_warden(client, warden):
    return client.post(
        "/login",
        data={"email": warden.email, "password": "WardenPass123!"},
    )


def test_warden_can_view_mess_menu(client, warden):
    _login_warden(client, warden)
    response = client.get("/warden/mess-menu/")
    assert response.status_code == 200
    assert b"Manage Mess Menu" in response.data


def test_student_cannot_access_mess_menu(logged_in_client):
    response = logged_in_client.get("/warden/mess-menu/")
    assert response.status_code == 403


def test_unauthenticated_user_cannot_access_mess_menu(client):
    response = client.get("/warden/mess-menu/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_warden_can_create_mess_menu(client, app, warden):
    from app.models import MessMenu

    _login_warden(client, warden)
    response = client.post(
        "/warden/mess-menu/",
        data={
            "day_of_week": "Monday",
            "meal_type": "Breakfast",
            "menu_items": "Idli and sambar",
            "start_time": "07:00",
            "end_time": "09:00",
        },
    )
    assert response.status_code == 302

    with app.app_context():
        menu = MessMenu.query.filter_by(
            day_of_week="Monday",
            meal_type="Breakfast",
        ).one()
        assert menu.menu_items == "Idli and sambar"
        assert menu.is_available is True


def test_warden_cannot_create_duplicate_mess_menu(client, app, warden):
    from datetime import time
    from app import db
    from app.models import MessMenu

    with app.app_context():
        db.session.add(
            MessMenu(
                day_of_week="Monday",
                meal_type="Breakfast",
                menu_items="Idli",
                start_time=time(7, 0),
                end_time=time(9, 0),
            )
        )
        db.session.commit()

    _login_warden(client, warden)
    response = client.post(
        "/warden/mess-menu/",
        data={
            "day_of_week": "Monday",
            "meal_type": "Breakfast",
            "menu_items": "Dosa",
            "start_time": "07:00",
            "end_time": "09:00",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"already exists" in response.data


def test_warden_can_update_mess_menu(client, app, warden):
    from datetime import time
    from app import db
    from app.models import MessMenu

    with app.app_context():
        menu = MessMenu(
            day_of_week="Monday",
            meal_type="Breakfast",
            menu_items="Idli",
            start_time=time(7, 0),
            end_time=time(9, 0),
        )
        db.session.add(menu)
        db.session.commit()
        menu_id = menu.id

    _login_warden(client, warden)
    response = client.post(
        f"/warden/mess-menu/{menu_id}/update",
        data={
            "day_of_week": "Monday",
            "meal_type": "Breakfast",
            "menu_items": "Idli and chutney",
            "start_time": "07:30",
            "end_time": "09:30",
            "is_available": "on",
        },
    )
    assert response.status_code == 302

    with app.app_context():
        menu = db.session.get(MessMenu, menu_id)
        assert menu.menu_items == "Idli and chutney"
        assert menu.is_available is True


def test_warden_can_delete_unregistered_mess_menu(client, app, warden):
    from datetime import time
    from app import db
    from app.models import MessMenu

    with app.app_context():
        menu = MessMenu(
            day_of_week="Monday",
            meal_type="Breakfast",
            menu_items="Idli",
            start_time=time(7, 0),
            end_time=time(9, 0),
        )
        db.session.add(menu)
        db.session.commit()
        menu_id = menu.id

    _login_warden(client, warden)
    response = client.post(f"/warden/mess-menu/{menu_id}/delete")
    assert response.status_code == 302

    with app.app_context():
        assert db.session.get(MessMenu, menu_id) is None


def test_warden_rejects_invalid_weekday_and_meal_type(client, warden):
    _login_warden(client, warden)
    response = client.post(
        "/warden/mess-menu/",
        data={
            "day_of_week": "Funday",
            "meal_type": "Brunch",
            "menu_items": "Pancakes",
            "start_time": "07:00",
            "end_time": "09:00",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Choose a valid day and meal type." in response.data


def test_warden_rejects_empty_menu_items(client, warden):
    _login_warden(client, warden)
    response = client.post(
        "/warden/mess-menu/",
        data={
            "day_of_week": "Monday",
            "meal_type": "Breakfast",
            "menu_items": "   ",
            "start_time": "07:00",
            "end_time": "09:00",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Menu items are required" in response.data


def test_warden_rejects_invalid_or_reversed_meal_timings(client, warden):
    _login_warden(client, warden)

    response = client.post(
        "/warden/mess-menu/",
        data={
            "day_of_week": "Monday",
            "meal_type": "Breakfast",
            "menu_items": "Idli",
            "start_time": "invalid",
            "end_time": "09:00",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Enter valid meal start and end times." in response.data

    response = client.post(
        "/warden/mess-menu/",
        data={
            "day_of_week": "Monday",
            "meal_type": "Breakfast",
            "menu_items": "Idli",
            "start_time": "09:00",
            "end_time": "07:00",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"The end time must be later than the start time." in response.data


def test_warden_cannot_update_menu_to_duplicate_day_and_meal(
    client, app, warden
):
    with app.app_context():
        first = MessMenu(
            day_of_week="Monday",
            meal_type="Breakfast",
            menu_items="Idli",
            start_time=time(7, 0),
            end_time=time(9, 0),
        )
        second = MessMenu(
            day_of_week="Tuesday",
            meal_type="Lunch",
            menu_items="Rice",
            start_time=time(12, 0),
            end_time=time(14, 0),
        )
        db.session.add_all([first, second])
        db.session.commit()
        second_id = second.id

    _login_warden(client, warden)
    response = client.post(
        f"/warden/mess-menu/{second_id}/update",
        data={
            "day_of_week": "Monday",
            "meal_type": "Breakfast",
            "menu_items": "Updated menu",
            "start_time": "07:30",
            "end_time": "09:30",
            "is_available": "on",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Another menu entry already exists" in response.data

    with app.app_context():
        second = db.session.get(MessMenu, second_id)
        assert second.day_of_week == "Tuesday"
        assert second.meal_type == "Lunch"


def test_warden_cannot_delete_menu_with_registrations(client, app, warden):
    from app.models import MealRegistration, Student

    with app.app_context():
        menu = MessMenu(
            day_of_week="Monday",
            meal_type="Breakfast",
            menu_items="Idli",
            start_time=time(7, 0),
            end_time=time(9, 0),
        )
        student = Student(
            full_name="Registered Student",
            email="registered.student@example.com",
            password_hash=generate_password_hash("StudentPass123!"),
            contact_number="9876543210",
            srn="TEST-SRN-003",
            parent_name="Test Parent",
            parent_contact_number="9876543211",
            hostel_name="Test Hostel",
            room_number="101",
            id_proof_filename="test_id.pdf",
        )
        db.session.add_all([menu, student])
        db.session.commit()

        registration = MealRegistration(
            student_id=student.id,
            menu_id=menu.id,
        )
        db.session.add(registration)
        db.session.commit()
        menu_id = menu.id

    _login_warden(client, warden)
    response = client.post(
        f"/warden/mess-menu/{menu_id}/delete",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"has registrations and cannot be deleted" in response.data

    with app.app_context():
        assert db.session.get(MessMenu, menu_id) is not None
        assert MealRegistration.query.filter_by(menu_id=menu_id).count() == 1


def test_warden_can_mark_mess_menu_unavailable(client, app, warden):
    with app.app_context():
        menu = MessMenu(
            day_of_week="Monday",
            meal_type="Breakfast",
            menu_items="Idli",
            start_time=time(7, 0),
            end_time=time(9, 0),
            is_available=True,
        )
        db.session.add(menu)
        db.session.commit()
        menu_id = menu.id

    _login_warden(client, warden)
    response = client.post(
        f"/warden/mess-menu/{menu_id}/update",
        data={
            "day_of_week": "Monday",
            "meal_type": "Breakfast",
            "menu_items": "Idli",
            "start_time": "07:00",
            "end_time": "09:00",
        },
    )
    assert response.status_code == 302

    with app.app_context():
        menu = db.session.get(MessMenu, menu_id)
        assert menu.is_available is False
