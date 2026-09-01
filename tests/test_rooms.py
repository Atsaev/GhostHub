import shutil
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from app.common.datetime import utc_now
from app.common.storage import buffer_path
from app.core.config import settings
from app.database.session import async_session_factory
from app.modules.room.models import Room
from app.modules.room.service import (
    cleanup_expired_rooms,
    cleanup_orphan_files,
    create_room,
    get_room_any,
)


def test_device_id_cookie_matches_page(client):
    response = client.post("/rooms", data={}, follow_redirects=False)
    room_path = response.headers["location"]

    page = client.get(room_path)
    assert page.status_code == 200
    cookie = client.cookies.get("device_id")
    assert cookie
    assert f'data-device-id="{cookie}"' in page.text


def test_base_path_prefix(client, monkeypatch):
    from app.common.templating import template_engine
    from app.core.config import settings

    monkeypatch.setattr(settings, "base_path", "/ghost")
    template_engine.engine.globals["base_path"] = "/ghost"
    try:
        response = client.post("/rooms", data={}, follow_redirects=False)
        assert response.status_code == 303
        room_path = response.headers["location"]
        assert room_path.startswith("/ghost/rooms/")
        token = room_path.rsplit("/", 1)[1]

        # прямой доступ без префикса (префикс срезает обратный прокси)
        page = client.get(f"/rooms/{token}").text
        assert 'sse-connect="/ghost/rooms/' in page
        assert "/ghost/static/style.css" in page
        assert f"/ghost/rooms/{token}/qr.svg" in page
    finally:
        template_engine.engine.globals["base_path"] = ""


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
        assert room is not None
        room.expires_at = utc_now() - timedelta(seconds=1)
        await session.commit()

    tokens = await cleanup_expired_rooms()
    assert tokens == [token]
    assert await get_room_any(token) is None


async def test_cleanup_orphan_files():
    storage_root = Path(settings.storage_path)
    if storage_root.is_dir():
        shutil.rmtree(storage_root)

    room = await create_room("gggggggggggggggg")
    orphan = buffer_path(room.id, uuid4())
    orphan.parent.mkdir(parents=True, exist_ok=True)
    orphan.write_bytes(b"orphan data")

    removed = await cleanup_orphan_files()

    assert removed == 1
    assert not orphan.exists()


def test_create_room_rate_limit(client):
    from app.common import rate_limit

    rate_limit.room_creation_limiter.limit = 2
    rate_limit.room_creation_limiter._events.clear()

    assert client.post("/rooms", data={}, follow_redirects=False).status_code == 303
    assert client.post("/rooms", data={}, follow_redirects=False).status_code == 303
    assert client.post("/rooms", data={}, follow_redirects=False).status_code == 429


def test_join_attempt_rate_limit(client):
    from app.common import rate_limit

    rate_limit.room_creation_limiter.limit = 20
    rate_limit.room_creation_limiter._events.clear()
    rate_limit.join_attempt_limiter.limit = 2
    rate_limit.join_attempt_limiter._events.clear()

    response = client.post("/rooms", data={"password": "secret"}, follow_redirects=False)
    room_path = response.headers["location"]

    client.post(f"{room_path}/join", data={"password": "wrong"}, follow_redirects=False)
    client.post(f"{room_path}/join", data={"password": "wrong"}, follow_redirects=False)
    response = client.post(f"{room_path}/join", data={"password": "wrong"}, follow_redirects=False)

    assert "Слишком много попыток" in response.text
