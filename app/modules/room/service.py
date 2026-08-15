from datetime import timedelta

from sqlalchemy import select

from app.common.datetime import utc_now
from app.core.config import settings
from app.database.session import async_session_factory
from app.modules.room.models import Room


async def create_room(public_token: str) -> Room:
    now = utc_now()

    room = Room(
        public_token=public_token,
        created_at=now,
        expires_at=now + timedelta(
            seconds=settings.room_ttl_seconds,
        ),
    )
    async with async_session_factory() as session:
        session.add(room)
        await session.commit()

        return room


async def get_room(public_token: str) -> Room | None:
    async with async_session_factory() as session:
        result = await session.execute(
            select(Room).where(
                Room.public_token == public_token,
                Room.expires_at > utc_now(),
            )
        )

        return result.scalar_one_or_none()
