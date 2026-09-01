from typing import Annotated
from uuid import UUID

from litestar import Request, Response, get, post
from litestar.datastructures import UploadFile
from litestar.enums import RequestEncodingType
from litestar.exceptions import HTTPException, NotFoundException
from litestar.params import Body, FromPath
from litestar.response import File
from pydantic import BaseModel, ConfigDict

from app.common.device import get_or_set_device_id
from app.common.security import verify_room_token
from app.common.storage import BufferLimitError, buffer_path
from app.common.templating import render_fragment
from app.modules.buffer.service import (
    MAX_TEXT_LENGTH,
    create_file_message,
    create_text_message,
    get_message,
)
from app.modules.room.models import Room
from app.modules.room.service import get_room, publish_room_update


class CreateMessageForm(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    content: str | None = None
    file: UploadFile | None = None


@post("/rooms/{public_token:str}/messages", name="room_messages_create")
async def room_messages_create(
    request: Request,
    public_token: FromPath[str],
    data: Annotated[CreateMessageForm, Body(media_type=RequestEncodingType.MULTI_PART)],
) -> Response:
    room = await get_room(public_token)
    if room is None:
        raise NotFoundException("Комната не найдена или истекла")
    if not _room_authenticated(request, room):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    response = Response(content=b"", status_code=204)
    device_id = get_or_set_device_id(request, response)

    if data.file is not None and data.file.filename:
        try:
            await create_file_message(room.id, device_id, data.file)
        except BufferLimitError as exc:
            return _toast_response(413, str(exc))
    else:
        text = (data.content or "").strip()
        if not text:
            return _toast_response(400, "Пустое сообщение")
        if len(text) > MAX_TEXT_LENGTH:
            return _toast_response(400, "Сообщение слишком длинное")
        await create_text_message(room.id, device_id, text)

    await publish_room_update(room)
    return response


@get("/rooms/{public_token:str}/files/{buffer_id:uuid}", name="room_file_download")
async def room_file_download(
    request: Request,
    public_token: FromPath[str],
    buffer_id: FromPath[UUID],
) -> File:
    room = await get_room(public_token)
    if room is None:
        raise NotFoundException("Комната не найдена или истекла")
    if not _room_authenticated(request, room):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    message = await get_message(room.id, buffer_id)
    if message is None or message.kind != "file":
        raise NotFoundException("Файл не найден")
    path = buffer_path(room.id, message.id)
    if not path.is_file():
        raise NotFoundException("Файл не найден")
    return File(
        path=path,
        filename=message.file_name or "file",
        media_type=message.mime_type or "application/octet-stream",
    )


def _toast_response(status_code: int, message: str) -> Response:
    return Response(
        content=render_fragment("partials/toast.html", message=message),
        status_code=status_code,
        media_type="text/html",
    )


def _room_authenticated(request: Request, room: Room) -> bool:
    if room.password_hash is None:
        return True
    signature = request.cookies.get(f"room_pass_{room.public_token}")
    return signature is not None and verify_room_token(room.public_token, signature)
