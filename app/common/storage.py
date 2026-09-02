import asyncio
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
    size = await _write_chunks(path, file, limit)
    return size


async def _write_chunks(path: Path, file: UploadFile, limit: int) -> int:
    """sync-запись чанка выносится в поток, чтобы не блокировать event loop."""
    size = 0
    try:
        with path.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > limit:
                    raise BufferLimitError(f"Файл превышает лимит {human_size(limit)}")
                await asyncio.to_thread(out.write, chunk)
        return size
    except BaseException:
        path.unlink(missing_ok=True)
        raise


async def delete_room_files(room_id: UUID) -> None:
    """Удаляет папку комнаты вне event loop."""
    room_dir = Path(settings.storage_path) / str(room_id)
    await asyncio.to_thread(shutil.rmtree, room_dir, ignore_errors=True)


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if value < 1024 or unit == "ТБ":
            return f"{value:.0f} {unit}"
        value /= 1024
    return f"{value:.0f} Б"
