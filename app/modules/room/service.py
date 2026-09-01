from datetime import UTC, timedelta
from uuid import UUID

from sqlalchemy import delete, func, select

from app.common.datetime import utc_now
from app.common.device import device_color, device_icon
from app.common.security import hash_password
from app.common.storage import delete_room_files, human_size
from app.common.templating import render_fragment
from app.core.config import settings
from app.core.hub import hub
from app.database.session import async_session_factory
from app.modules.buffer.models import Buffer
from app.modules.room.models import Room


async def create_room(public_token: str, password: str | None = None) -> Room:
    now = utc_now()
    room = Room(
        public_token=public_token,
        password_hash=hash_password(password) if password else None,
        created_at=now,
        expires_at=now + timedelta(seconds=settings.room_ttl_seconds),
    )
    async with async_session_factory() as session:
        session.add(room)
        await session.commit()
    return room


async def get_room(public_token: str) -> Room | None:
    """Живая комната (не истекла)."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(Room).where(
                Room.public_token == public_token,
                Room.expires_at > utc_now(),
            )
        )
        return result.scalar_one_or_none()


async def get_room_any(public_token: str) -> Room | None:
    async with async_session_factory() as session:
        result = await session.execute(
            select(Room).where(Room.public_token == public_token)
        )
        return result.scalar_one_or_none()


async def delete_room(room_id: UUID) -> None:
    """Удаляет сообщения, комнату и файлы с диска."""
    async with async_session_factory() as session:
        await session.execute(delete(Buffer).where(Buffer.room_id == room_id))
        await session.execute(delete(Room).where(Room.id == room_id))
        await session.commit()
    delete_room_files(room_id)


async def cleanup_expired_rooms() -> list[str]:
    async with async_session_factory() as session:
        result = await session.execute(
            select(Room).where(Room.expires_at <= utc_now())
        )
        rooms = list(result.scalars().all())
    for room in rooms:
        await delete_room(room.id)
    return [room.public_token for room in rooms]


async def room_storage_bytes(room_id: UUID) -> int:
    """Суммарный размер файлов комнаты в байтах."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(func.coalesce(func.sum(Buffer.file_size), 0)).where(
                Buffer.room_id == room_id,
                Buffer.kind == "file",
            )
        )
        value = result.scalar_one()
        return int(value) if value is not None else 0


async def list_messages(room_id: UUID) -> list[Buffer]:
    async with async_session_factory() as session:
        result = await session.execute(
            select(Buffer)
            .where(Buffer.room_id == room_id)
            .order_by(Buffer.created_at.asc())
        )
        return list(result.scalars().all())


def message_view(message: Buffer, token: str) -> dict:
    created = message.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    return {
        "id": str(message.id),
        "kind": message.kind,
        "content": message.content,
        "file_name": message.file_name,
        "file_size_str": human_size(message.file_size) if message.file_size else "",
        "icon": device_icon(message.device_id),
        "color": device_color(message.device_id),
        "time_str": created.astimezone().strftime("%H:%M"),
        "download_url": (
            f"/rooms/{token}/files/{message.id}" if message.kind == "file" else ""
        ),
    }


def storage_context(used: int) -> dict:
    limit = settings.room_max_bytes
    percent = min(100, int(used * 100 / limit)) if limit else 0
    return {
        "storage_used_str": human_size(used),
        "storage_max_str": human_size(limit),
        "storage_percent": percent,
    }


async def publish_room_update(room: Room) -> None:
    """Рассчитывает свежие фрагменты и рассылает их подписчикам комнаты."""
    messages = await list_messages(room.id)
    message_html = render_fragment(
        "partials/messages.html",
        messages=[message_view(m, room.public_token) for m in messages],
        token=room.public_token,
    )
    stats_html = render_fragment("partials/stats.html", **storage_context(await room_storage_bytes(room.id)))
    await hub.publish(room.public_token, "message", message_html)
    await hub.publish(room.public_token, "stats", stats_html)
