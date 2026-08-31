import io
import secrets
from collections.abc import AsyncIterator
from uuid import uuid4

import qrcode
from qrcode.image.svg import SvgImage
from litestar import Request, Response, get, post
from litestar.exceptions import NotFoundException
from litestar.params import Form
from litestar.response import RedirectResponse, StreamingResponse, Template

from app.common.datetime import utc_now
from app.common.device import device_color, device_icon
from app.common.security import sign_room_token, verify_password, verify_room_token
from app.core.config import settings
from app.core.hub import hub
from app.modules.room.models import Room
from app.modules.room.service import (
    create_room,
    get_room,
    get_room_any,
    list_messages,
    message_view,
    room_storage_bytes,
    storage_context,
)


@get("/", name="index")
async def index_endpoint() -> Template:
    return Template(template_name="index.html")


@post("/rooms", name="create_room")
async def create_room_endpoint(password: str | None = Form(None)) -> RedirectResponse:
    public_token = secrets.token_urlsafe(12)[:16]
    room = await create_room(public_token, password=password or None)
    return RedirectResponse(f"/rooms/{room.public_token}", status_code=303)


@get("/rooms/{public_token:str}", name="room_page")
async def room_page(request: Request, public_token: str) -> Template:
    room = await get_room_any(public_token)
    if room is None or room.expires_at <= utc_now():
        return _room_template(request, public_token, {"expired": True})

    context: dict = {
        "room": room,
        "room_url": _room_url(request, public_token),
    }
    if room.password_hash is not None:
        context["password_protected"] = True
        if not _room_authenticated(request, room):
            context["locked"] = True
            return _room_template(request, public_token, context)

    messages = await list_messages(room.id)
    used = await room_storage_bytes(room.id)
    device_id = request.cookies.get("device_id") or uuid4().hex
    context.update(
        {
            "messages": [message_view(m, public_token) for m in messages],
            **storage_context(used),
            "device": {
                "icon": device_icon(device_id),
                "color": device_color(device_id),
            },
            "ttl_minutes": max(
                0,
                int((room.expires_at - utc_now()).total_seconds() // 60),
            ),
        }
    )
    return _room_template(request, public_token, context)


@post("/rooms/{public_token:str}/join", name="room_join")
async def room_join(
    request: Request,
    public_token: str,
    password: str = Form(...),
) -> Response:
    room = await get_room_any(public_token)
    if room is None or room.expires_at <= utc_now():
        return _room_template(request, public_token, {"expired": True})
    if room.password_hash is None:
        return RedirectResponse(f"/rooms/{public_token}", status_code=303)
    if not verify_password(password, room.password_hash):
        context = {
            "room": room,
            "room_url": _room_url(request, public_token),
            "password_protected": True,
            "locked": True,
            "error": "Неверный пароль",
        }
        return _room_template(request, public_token, context)

    response = RedirectResponse(f"/rooms/{public_token}", status_code=303)
    response.set_cookie(
        f"room_pass_{public_token}",
        sign_room_token(public_token),
        max_age=settings.room_ttl_seconds,
        path=f"/rooms/{public_token}",
        httponly=True,
        samesite="lax",
    )
    return response


@get("/rooms/{public_token:str}/events", name="room_events")
async def room_events(public_token: str) -> StreamingResponse:
    async def stream() -> AsyncIterator[str]:
        queue = await hub.subscribe(public_token)
        try:
            yield ": connected\n\n"
            while True:
                payload = await queue.get()
                yield payload
        finally:
            await hub.unsubscribe(public_token, queue)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


@get("/rooms/{public_token:str}/qr.svg", name="room_qr")
async def room_qr(request: Request, public_token: str) -> Response:
    room = await get_room(public_token)
    if room is None:
        raise NotFoundException("Комната не найдена или истекла")
    url = _room_url(request, public_token)
    image = qrcode.make(url, image_factory=SvgImage, border=2)
    buffer = io.BytesIO()
    image.save(buffer)
    return Response(
        content=buffer.getvalue(),
        media_type="image/svg+xml",
        headers={"Cache-Control": "no-store"},
    )


def _room_url(request: Request, public_token: str) -> str:
    if settings.public_base_url:
        base = settings.public_base_url.rstrip("/")
    else:
        base = str(request.base_url).rstrip("/")
    return f"{base}/rooms/{public_token}"


def _room_authenticated(request: Request, room: Room) -> bool:
    if room.password_hash is None:
        return True
    signature = request.cookies.get(f"room_pass_{room.public_token}")
    return signature is not None and verify_room_token(room.public_token, signature)


def _room_template(request: Request, public_token: str, context: dict) -> Template:
    response = Template(
        template_name="room.html",
        context={"token": public_token, **context},
    )
    if request.cookies.get("device_id") is None:
        response.set_cookie(
            "device_id",
            uuid4().hex,
            max_age=315_360_000,
            path="/",
            httponly=True,
            samesite="lax",
        )
    return response
