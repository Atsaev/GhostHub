from uuid import UUID, uuid4

from litestar import Request, Response, get, post
from litestar.datastructures import UploadFile
from litestar.exceptions import HTTPException, NotFoundException
from litestar.params import File, Form
from litestar.response import FileResponse

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


@post("/rooms/{public_token:str}/messages", name="room_messages_create")
async def room_messages_create(
    request: Request,
    public_token: str,
    content: str | None = Form(None),
    file: UploadFile | None = File(None),
) -> Response:
    room = await get_room(public_token)
    if room is None:
        raise NotFoundException("Комната не найдена или истекла")
    if not _room_authenticated(request, room):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    response = Response(status_code=204)
    device_id = _get_or_set_device_id(request, response)

    if file is not None and file.filename:
        try:
            await create_file_message(room.id, device_id, file)
        except BufferLimitError as exc:
            return _toast_response(413, str(exc))
    else:
        text = (content or "").strip()
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
    public_token: str,
    buffer_id: UUID,
) -> FileResponse:
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
    return FileResponse(
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


def _get_or_set_device_id(request: Request, response: Response) -> str:
    device_id = request.cookies.get("device_id")
    if device_id is None or len(device_id) != 32:
        device_id = uuid4().hex
        response.set_cookie(
            "device_id",
            device_id,
            max_age=315_360_000,
            path="/",
            httponly=True,
            samesite="lax",
        )
    return device_id
