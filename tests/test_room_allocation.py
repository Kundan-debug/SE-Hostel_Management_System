import pytest

from app import db
from app.models import Room, Student


@pytest.fixture
def rooms(app):
    """Student starts in Test Hostel / 101 (record exists, 1 of 2 beds used)."""
    data = [
        Room(hostel_name="Test Hostel", room_number="101",
             capacity=2, occupied_beds=1),
        Room(hostel_name="Test Hostel", room_number="102",
             capacity=3, occupied_beds=1),
        Room(hostel_name="Test Hostel", room_number="103",
             capacity=2, occupied_beds=2),
        Room(hostel_name="Test Hostel", room_number="104",
             capacity=2, occupied_beds=0,
             maintenance_status="Under Maintenance"),
        Room(hostel_name="Other Hostel", room_number="201",
             capacity=4, occupied_beds=0),
    ]
    db.session.add_all(data)
    db.session.commit()
    return {room.room_number: room.id for room in data}


def get_room(room_id):
    return db.session.get(Room, room_id)


def get_student():
    return Student.query.filter_by(email="student@gmail.com").one()


# Access control


def test_allocation_page_requires_login(client):
    response = client.get("/room-details/allocation")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


# Viewing rooms


def test_allocation_page_lists_rooms_and_states(logged_in_client, rooms):
    response = logged_in_client.get("/room-details/allocation")

    assert response.status_code == 200
    assert b"Room Availability" in response.data
    assert b"Your room" in response.data
    assert b"Vacant" in response.data
    assert b"Full" in response.data
    assert b"Under maintenance" in response.data


def test_allocation_page_filters_by_hostel(logged_in_client, rooms):
    response = logged_in_client.get(
        "/room-details/allocation?hostel=Other Hostel"
    )

    assert response.status_code == 200
    assert b"201" in response.data
    assert b"<td>102</td>" not in response.data


def test_allocation_page_with_no_rooms(logged_in_client):
    response = logged_in_client.get("/room-details/allocation")

    assert response.status_code == 200
    assert b"No rooms have been recorded yet." in response.data


def test_room_details_links_to_allocation(logged_in_client, rooms):
    response = logged_in_client.get("/room-details/")

    assert response.status_code == 200
    assert b"/room-details/allocation" in response.data


# Students cannot change their own room


def test_page_offers_no_allocate_or_transfer_controls(
    logged_in_client, rooms
):
    response = logged_in_client.get("/room-details/allocation")

    assert b"<form method=\"POST\"" not in response.data
    assert b"Transfer here" not in response.data
    assert b"Allocate" not in response.data


@pytest.mark.parametrize("method", ["post", "get", "put"])
def test_allocate_endpoint_no_longer_exists(logged_in_client, rooms, method):
    response = getattr(logged_in_client, method)(
        "/room-details/allocate", data={"room_id": rooms["102"]}
    )

    assert response.status_code in (404, 405)


def test_student_room_and_occupancy_unchanged_after_attempt(
    logged_in_client, rooms
):
    logged_in_client.post(
        "/room-details/allocate", data={"room_id": rooms["102"]}
    )

    student = get_student()
    assert (student.hostel_name, student.room_number) == (
        "Test Hostel", "101"
    )
    assert get_room(rooms["101"]).occupied_beds == 1
    assert get_room(rooms["102"]).occupied_beds == 1


@pytest.mark.parametrize("field", ["room_number", "hostel_name"])
def test_profile_update_cannot_change_room(logged_in_client, rooms, field):
    logged_in_client.post(
        "/profile/edit", data={field: "999", "full_name": "Test Student"}
    )

    student = get_student()
    assert (student.hostel_name, student.room_number) == (
        "Test Hostel", "101"
    )
