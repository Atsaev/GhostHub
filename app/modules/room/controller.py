import asyncio
import io
import json
import secrets
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import uuid4

import qrcode
from litestar import Request, Response, get, post
from litestar.enums import RequestEncodingType
from litestar.exceptions import HTTPException, NotFoundException
from litestar.params import Body, FromPath
from litestar.response import Redirect, Stream, Template
from pydantic import BaseModel
from qrcode.image.svg import SvgImage

from app.common.datetime import utc_now
from app.common.device import device_color, device_icon, get_or_set_device_id
from app.common.rate_limit import join_attempt_limiter, room_creation_limiter
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


class CreateRoomForm(BaseModel):
    password: str | None = None


class JoinRoomForm(BaseModel):
    password: str


class RtcSignalForm(BaseModel):
    to: str
    data: str = ""


class RtcAcceptForm(BaseModel):
    to: str
    accept: bool = False


@get("/", name="index")
async def index_endpoint() -> Template:
    return Template(template_name="index.html")


@post("/rooms", name="create_room")
async def create_room_endpoint(
    request: Request,
    data: Annotated[CreateRoomForm, Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Response:
    if not room_creation_limiter.allow(_client_ip(request)):
        return Template(
            template_name="index.html",
            context={
                "error": "Слишком много комнат создаётся с этого адреса, попробуйте позже",
            },
            status_code=429,
        )
    public_token = secrets.token_urlsafe(12)[:16]
    room = await create_room(public_token, password=data.password or None)
    return Redirect(f"/rooms/{room.public_token}", status_code=303)


@get("/rooms/{public_token:str}", name="room_page")
async def room_page(request: Request, public_token: FromPath[str]) -> Template:
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
            "device_id": device_id,
            "stun_url": settings.p2p_stun_url,
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
    public_token: FromPath[str],
    data: Annotated[JoinRoomForm, Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Response:
    room = await get_room_any(public_token)
    if room is None or room.expires_at <= utc_now():
        return _room_template(request, public_token, {"expired": True})
    if room.password_hash is None:
        return Redirect(f"/rooms/{public_token}", status_code=303)
    if not verify_password(data.password, room.password_hash):
        if not join_attempt_limiter.allow(_client_ip(request)):
            context = {
                "room": room,
                "room_url": _room_url(request, public_token),
                "password_protected": True,
                "locked": True,
                "error": "Слишком много попыток входа, попробуйте позже",
            }
            return _room_template(request, public_token, context)
        context = {
            "room": room,
            "room_url": _room_url(request, public_token),
            "password_protected": True,
            "locked": True,
            "error": "Неверный пароль",
        }
        return _room_template(request, public_token, context)

    response = Redirect(f"/rooms/{public_token}", status_code=303)
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
async def room_events(request: Request, public_token: FromPath[str]) -> Stream:
    device_id = request.cookies.get("device_id")
    queue = await hub.subscribe(public_token, device_id)

    async def stream() -> AsyncIterator[str]:
        try:
            yield "retry: 3000\n\n"
            yield ": connected\n\n"
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=25)
                except TimeoutError:
                    # keep-alive пинг, чтобы соединение не закрывали прокси
                    yield ": ping\n\n"
                    continue
                yield payload
        finally:
            await hub.unsubscribe(public_token, queue, device_id)

    return Stream(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@get("/rooms/{public_token:str}/devices", name="room_devices")
async def room_devices(request: Request, public_token: FromPath[str]) -> dict:
    """Список устройств, находящихся в комнате сейчас (без текущего)."""
    room = await get_room(public_token)
    if room is None:
        raise NotFoundException("Комната не найдена или истекла")
    if not _room_authenticated(request, room):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    self_id = request.cookies.get("device_id")
    devices = [
        {
            "id": device_id,
            "icon": device_icon(device_id),
            "color": device_color(device_id),
            "short": device_id[:6],
        }
        for device_id in hub.online_devices(public_token)
        if device_id and device_id != self_id
    ]
    return {"devices": devices}


@get("/rooms/{public_token:str}/qr.svg", name="room_qr")
async def room_qr(request: Request, public_token: FromPath[str]) -> Response:
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


@post("/rooms/{public_token:str}/rtc/{kind:str}", name="rtc_signal")
async def rtc_signal(
    request: Request,
    public_token: FromPath[str],
    kind: FromPath[str],
    data: Annotated[RtcSignalForm, Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Response:
    """Ретранслирует webrtc-сигнал (offer/answer/ice) между устройствами комнаты."""
    if kind not in ("offer", "answer", "ice"):
        raise NotFoundException("Неизвестный тип сигнала")
    room = await get_room(public_token)
    if room is None:
        raise NotFoundException("Комната не найдена или истекла")
    if not _room_authenticated(request, room):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    response = Response(content=b"", status_code=204)
    sender = get_or_set_device_id(request, response)
    await hub.publish(
        public_token,
        f"rtc-{kind}",
        json.dumps({"from": sender, "data": data.data}, ensure_ascii=False),
    )
    return response


@post("/rooms/{public_token:str}/rtc/accept", name="rtc_accept")
async def rtc_accept(
    request: Request,
    public_token: FromPath[str],
    data: Annotated[RtcAcceptForm, Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Response:
    """Сообщает отправителю о согласии/отказе получателя."""
    room = await get_room(public_token)
    if room is None:
        raise NotFoundException("Комната не найдена или истекла")
    if not _room_authenticated(request, room):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    response = Response(content=b"", status_code=204)
    sender = get_or_set_device_id(request, response)
    await hub.publish(
        public_token,
        "rtc-accept",
        json.dumps({"from": sender, "accept": data.accept}, ensure_ascii=False),
    )
    return response


def _room_url(request: Request, public_token: str) -> str:
    if settings.public_base_url:
        base = settings.public_base_url.rstrip("/")
    else:
        base = str(request.base_url).rstrip("/")
    return f"{base}/rooms/{public_token}"


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


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
