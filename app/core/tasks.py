import asyncio
import logging

from litestar import Litestar

from app.core.config import settings
from app.core.hub import hub
from app.modules.room.service import cleanup_expired_rooms

logger = logging.getLogger(__name__)


async def _cleanup_loop() -> None:
    while True:
        await asyncio.sleep(settings.room_cleanup_interval_seconds)
        try:
            expired_tokens = await cleanup_expired_rooms()
            for token in expired_tokens:
                await hub.publish(token, "expired", "")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Ошибка фоновой очистки комнат")


async def start_cleanup_task(app: Litestar) -> None:
    app.state.cleanup_task = asyncio.create_task(_cleanup_loop())


async def stop_cleanup_task(app: Litestar) -> None:
    task = getattr(app.state, "cleanup_task", None)
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
