import re


def _create_room(client) -> str:
    response = client.post("/rooms", data={}, follow_redirects=False)
    room_path = response.headers["location"]
    client.get(room_path)
    return room_path


def test_text_message(client):
    room_path = _create_room(client)
    response = client.post(
        f"{room_path}/messages",
        data={"content": "привет"},
        files={"file": ("", b"", "text/plain")},
        follow_redirects=False,
    )
    assert response.status_code == 204
    assert "привет" in client.get(room_path).text


def test_empty_message_rejected(client):
    room_path = _create_room(client)
    response = client.post(
        f"{room_path}/messages",
        data={"content": "   "},
        files={"file": ("", b"", "text/plain")},
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "Пустое сообщение" in response.text


def test_file_upload_and_download(client):
    room_path = _create_room(client)
    response = client.post(
        f"{room_path}/messages",
        files={"file": ("hello.txt", b"hello world", "text/plain")},
        follow_redirects=False,
    )
    assert response.status_code == 204

    page = client.get(room_path)
    assert "hello.txt" in page.text
    match = re.search(rf"{room_path}/files/([0-9a-f-]+)", page.text)
    assert match is not None

    downloaded = client.get(match.group(0))
    assert downloaded.status_code == 200
    assert downloaded.content == b"hello world"


def test_size_limit(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "room_max_bytes", 10)
    room_path = _create_room(client)
    response = client.post(
        f"{room_path}/messages",
        files={"file": ("big.bin", b"x" * 100, "application/octet-stream")},
        follow_redirects=False,
    )
    assert response.status_code == 413
    assert "превышает лимит" in response.text


def test_image_preview(client):
    room_path = _create_room(client)
    response = client.post(
        f"{room_path}/messages",
        files={"file": ("photo.png", b"\x89PNG\r\n\x1a\n", "image/png")},
        follow_redirects=False,
    )
    assert response.status_code == 204

    page = client.get(room_path)
    assert "file-card-image" in page.text
    assert "<img" in page.text


def test_self_message_has_no_send_button(client):
    import asyncio

    from app.modules.buffer.service import create_text_message
    from app.modules.room.service import get_room_any

    room_path = _create_room(client)
    token = room_path.rsplit("/", 1)[1]

    client.post(
        f"{room_path}/messages",
        data={"content": "моё сообщение"},
        files={"file": ("", b"", "text/plain")},
        follow_redirects=False,
    )

    async def add_foreign_message():
        room = await get_room_any(token)
        assert room is not None
        await create_text_message(room.id, "f" * 32, "чужое сообщение")

    asyncio.run(add_foreign_message())

    page = client.get(room_path).text
    # кнопка передачи (📤 + аватар) только у чужого сообщения
    assert page.count("data-send-to") == 2


def test_qr_code(client):
    room_path = _create_room(client)
    response = client.get(f"{room_path}/qr.svg")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/svg+xml"
