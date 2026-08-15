import secrets

from litestar import get, post
from litestar.exceptions import NotFoundException

from app.modules.room.service import create_room, get_room


@post("/rooms")
async def create_room_endpoint() -> dict:
    public_token = secrets.token_urlsafe(12)[:16]

    room = await create_room(public_token)

    return {
        "id": str(room.id),
        "public_token": room.public_token,
        "created_at": room.created_at,
        "expires_at": room.expires_at,
    }


@get("/rooms/{public_token:str}")
async def get_room_endpoint(public_token: str) -> dict:
    room = await get_room(public_token)

    if room is None:
        raise NotFoundException("Room not found")

    return {
        "id": str(room.id),
        "public_token": room.public_token,
        "created_at": room.created_at,
        "expires_at": room.expires_at,
    }
