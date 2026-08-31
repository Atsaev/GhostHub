from uuid import UUID, uuid4

from litestar.datastructures import UploadFile
from sqlalchemy import select

from app.common.storage import BufferLimitError, save_buffer_file
from app.core.config import settings
from app.database.session import async_session_factory
from app.modules.buffer.models import Buffer
from app.modules.room.service import room_storage_bytes

MAX_TEXT_LENGTH = 10_000


async def create_text_message(room_id: UUID, device_id: str, content: str) -> Buffer:
    buffer = Buffer(
        room_id=room_id,
        kind="text",
        content=content,
        device_id=device_id,
    )
    async with async_session_factory() as session:
        session.add(buffer)
        await session.commit()
    return buffer


async def create_file_message(
    room_id: UUID,
    device_id: str,
    file: UploadFile,
) -> Buffer:
    used = await room_storage_bytes(room_id)
    if used >= settings.room_max_bytes:
        raise BufferLimitError("Лимит объёма комнаты исчерпан")

    buffer_id = uuid4()
    size = await save_buffer_file(
        room_id,
        buffer_id,
        file,
        settings.room_max_bytes - used,
    )
    buffer = Buffer(
        id=buffer_id,
        room_id=room_id,
        kind="file",
        content="",
        file_name=file.filename,
        file_size=size,
        mime_type=file.content_type or "application/octet-stream",
        device_id=device_id,
    )
    async with async_session_factory() as session:
        session.add(buffer)
        await session.commit()
    return buffer


async def get_message(room_id: UUID, buffer_id: UUID) -> Buffer | None:
    async with async_session_factory() as session:
        result = await session.execute(
            select(Buffer).where(
                Buffer.id == buffer_id,
                Buffer.room_id == room_id,
            )
        )
        return result.scalar_one_or_none()
