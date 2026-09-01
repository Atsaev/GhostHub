from pathlib import Path
from typing import Any, cast

from litestar import Litestar
from litestar.datastructures import CacheControlHeader
from litestar.static_files import create_static_files_router
from litestar.template import TemplateConfig

from app.common.templating import template_engine
from app.core.tasks import start_cleanup_task, stop_cleanup_task
from app.modules.buffer.controller import (
    room_file_download,
    room_messages_create,
)
from app.modules.room.controller import (
    create_room_endpoint,
    index_endpoint,
    room_devices,
    room_events,
    room_join,
    room_page,
    room_qr,
    rtc_accept,
    rtc_signal,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = Litestar(
    route_handlers=[
        create_static_files_router(
            path="/static",
            directories=[STATIC_DIR],
            # без кеша: обновления js/css должны сразу попадать в браузер
            cache_control=CacheControlHeader(max_age=0, no_cache=True),
        ),
        index_endpoint,
        create_room_endpoint,
        room_page,
        room_join,
        room_events,
        room_qr,
        room_devices,
        rtc_accept,
        rtc_signal,
        room_messages_create,
        room_file_download,
    ],
    template_config=TemplateConfig(engine=cast(Any, template_engine)),
    on_startup=[start_cleanup_task],
    on_shutdown=[stop_cleanup_task],
)
