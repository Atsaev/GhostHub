from datetime import timedelta

from app.common.datetime import utc_now
from app.database.session import async_session_factory
from app.modules.room.models import Room
from app.modules.room.service import cleanup_expired_rooms, create_room, get_room_any


def test_index_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "GhostHub" in response.text


def test_create_room_and_open_page(client):
    response = client.post("/rooms", data={}, follow_redirects=False)
    assert response.status_code == 303
    room_path = response.headers["location"]
    assert room_path.startswith("/rooms/")

    page = client.get(room_path)
    assert page.status_code == 200
    assert "sse-connect" in page.text
    assert "device_id" in client.cookies


def test_room_with_password(client):
    response = client.post("/rooms", data={"password": "secret"}, follow_redirects=False)
    room_path = response.headers["location"]
    token = room_path.rsplit("/", 1)[1]

    page = client.get(room_path)
    assert "паролем" in page.text
    assert "sse-connect" not in page.text

    wrong = client.post(f"{room_path}/join", data={"password": "wrong"}, follow_redirects=False)
    assert "Неверный пароль" in wrong.text

    ok = client.post(f"{room_path}/join", data={"password": "secret"}, follow_redirects=False)
    assert ok.status_code == 303
    assert f"room_pass_{token}" in client.cookies

    page = client.get(room_path)
    assert "sse-connect" in page.text


async def test_cleanup_deletes_expired_room():
    token = "cccccccccccccccc"
    room = await create_room(token, password=None)
    async with async_session_factory() as session:
        room = await session.get(Room, room.id)
        room.expires_at = utc_now() - timedelta(seconds=1)
        await session.commit()

    tokens = await cleanup_expired_rooms()
    assert tokens == [token]
    assert await get_room_any(token) is None
