"""extend rooms and buffers

Revision ID: a1b2c3d4e5f6
Revises: 8902e3771e0a
Create Date: 2026-08-30 22:58:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: str | Sequence[str] | None = "8902e3771e0a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "rooms", sa.Column("password_hash", sa.String(length=128), nullable=True)
    )
    op.create_index(op.f("ix_rooms_expires_at"), "rooms", ["expires_at"], unique=False)

    op.add_column(
        "buffers",
        sa.Column("kind", sa.String(length=8), server_default="text", nullable=False),
    )
    op.add_column(
        "buffers", sa.Column("file_name", sa.String(length=255), nullable=True)
    )
    op.add_column("buffers", sa.Column("file_size", sa.BigInteger(), nullable=True))
    op.add_column(
        "buffers", sa.Column("mime_type", sa.String(length=128), nullable=True)
    )
    op.add_column(
        "buffers",
        sa.Column(
            "device_id", sa.String(length=64), server_default="unknown", nullable=False
        ),
    )
    op.create_index(op.f("ix_buffers_room_id"), "buffers", ["room_id"], unique=False)
    op.create_index(
        op.f("ix_buffers_device_id"), "buffers", ["device_id"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_buffers_device_id"), table_name="buffers")
    op.drop_index(op.f("ix_buffers_room_id"), table_name="buffers")
    op.drop_column("buffers", "device_id")
    op.drop_column("buffers", "mime_type")
    op.drop_column("buffers", "file_size")
    op.drop_column("buffers", "file_name")
    op.drop_column("buffers", "kind")
    op.drop_index(op.f("ix_rooms_expires_at"), table_name="rooms")
    op.drop_column("rooms", "password_hash")
