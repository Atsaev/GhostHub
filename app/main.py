from litestar import Litestar

from app.modules.room.controller import (
    create_room_endpoint,
    get_room_endpoint,
)

app = Litestar(
    route_handlers=[
        create_room_endpoint,
        get_room_endpoint
    ],
)
