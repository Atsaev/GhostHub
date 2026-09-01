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


def test_qr_code(client):
    room_path = _create_room(client)
    response = client.get(f"{room_path}/qr.svg")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/svg+xml"
