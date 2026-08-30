from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
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
        index=True,
    )
    # "text" — сообщение, "file" — файл
    kind: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        default="text",
    )
    # текст сообщения; для файлов — пустая строка
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )
    file_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    file_size: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    mime_type: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    device_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
