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
