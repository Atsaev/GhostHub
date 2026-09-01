import asyncio

from app.core.hub import hub
from app.modules.buffer.service import create_text_message
from app.modules.room.service import create_room, publish_room_update


def _parse_sse(payload: str) -> tuple[str, str]:
    """Парсит sse-фрейм так же, как это делает EventSource в браузере."""
    event = "message"
    data_lines: list[str] = []
    for line in payload.split("\n"):
        if line.startswith("event:"):
            event = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].lstrip())
        elif line == "" and data_lines:
            break
    return event, "\n".join(data_lines)


async def test_sse_payload_keeps_multiline_html():
    room = await create_room("eeeeeeeeeeeeeeee")
    await create_text_message(room.id, "dev1", "первое сообщение\nсо второй строкой")

    queue = await hub.subscribe(room.public_token)
    try:
        await publish_room_update(room)
        payload = await asyncio.wait_for(queue.get(), timeout=1)
    finally:
        await hub.unsubscribe(room.public_token, queue)

    event, data = _parse_sse(payload)
    assert event == "message"
    assert "первое сообщение" in data
    assert "со второй строкой" in data
    assert 'class="msg"' in data


async def test_sse_payload_stats_event():
    room = await create_room("ffffffffffffffff")
    queue = await hub.subscribe(room.public_token)
    try:
        await publish_room_update(room)
        first = await asyncio.wait_for(queue.get(), timeout=1)
        second = await asyncio.wait_for(queue.get(), timeout=1)
    finally:
        await hub.unsubscribe(room.public_token, queue)

    events = [_parse_sse(first)[0], _parse_sse(second)[0]]
    assert set(events) == {"message", "stats"}


def test_rtc_signal_published_to_hub(client):
    import json

    response = client.post("/rooms", data={}, follow_redirects=False)
    room_path = response.headers["location"]
    token = room_path.rsplit("/", 1)[1]
    client.get(room_path)

    queue = asyncio.run(hub.subscribe(token))
    try:
        response = client.post(
            f"{room_path}/rtc/offer",
            data={"to": "abcdef0123456789", "data": "fake-sdp"},
            follow_redirects=False,
        )
        assert response.status_code == 204

        payload = asyncio.run(asyncio.wait_for(queue.get(), timeout=1))
        event, data = _parse_sse(payload)
        assert event == "rtc-offer"
        msg = json.loads(data)
        assert msg["data"] == "fake-sdp"
        assert msg["from"]
    finally:
        asyncio.run(hub.unsubscribe(token, queue))


def test_rtc_signal_requires_auth(client):
    response = client.post("/rooms", data={"password": "secret"}, follow_redirects=False)
    room_path = response.headers["location"]
    client.get(room_path)

    response = client.post(
        f"{room_path}/rtc/offer",
        data={"to": "abcdef0123456789", "data": "fake-sdp"},
        follow_redirects=False,
    )
    assert response.status_code == 403
