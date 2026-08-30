import shutil
from pathlib import Path
from uuid import UUID

from litestar.datastructures import UploadFile

from app.core.config import settings


class BufferLimitError(Exception):
    """Превышен лимит объёма файлов в комнате."""


def buffer_path(room_id: UUID, buffer_id: UUID) -> Path:
    return Path(settings.storage_path) / str(room_id) / str(buffer_id)


async def save_buffer_file(
    room_id: UUID,
    buffer_id: UUID,
    file: UploadFile,
    limit: int,
) -> int:
    """Пишет файл на диск чанками и возвращает его размер.

    При превышении limit удаляет частично записанный файл
    и бросает BufferLimitError.
    """
    path = buffer_path(room_id, buffer_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    try:
        with path.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise BufferLimitError(f"Файл превышает лимит {human_size(limit)}")
                out.write(chunk)
        return size
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def delete_room_files(room_id: UUID) -> None:
    room_dir = Path(settings.storage_path) / str(room_id)
    shutil.rmtree(room_dir, ignore_errors=True)


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if value < 1024 or unit == "ТБ":
            return f"{value:.0f} {unit}"
        value /= 1024
    return f"{value:.0f} Б"
