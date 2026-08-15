from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.common.datetime import utc_now
from app.database.base import Base


class Buffer(Base):
    __tablename__ = "buffers"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )
    room_id: Mapped[UUID] = mapped_column(
        ForeignKey("rooms.id"),
        nullable=False,
    )
    content: Mapped[UUID] = mapped_column(
        Text,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
