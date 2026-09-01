import asyncio
from collections import defaultdict


class RoomHub:
    """In-memory pub/sub для рассылки sse-событий по комнатам.

    Дополнительно отслеживает присутствие устройств: каждое живое
    sse-подключение регистрируется с device_id, что позволяет
    показывать список устройств, находящихся в комнате сейчас.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._presence: dict[str, dict[str, int]] = defaultdict(dict)
        self._lock = asyncio.Lock()

    async def subscribe(
        self,
        room_token: str,
        device_id: str | None = None,
    ) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._subscribers[room_token].add(queue)
            if device_id:
                self._presence[room_token][device_id] = (
                    self._presence[room_token].get(device_id, 0) + 1
                )
        return queue

    async def unsubscribe(
        self,
        room_token: str,
        queue: asyncio.Queue,
        device_id: str | None = None,
    ) -> None:
        async with self._lock:
            subscribers = self._subscribers.get(room_token)
            if subscribers is None:
                return
            subscribers.discard(queue)
            if not subscribers:
                self._subscribers.pop(room_token, None)
            if device_id:
                count = self._presence.get(room_token, {}).get(device_id, 0) - 1
                if count <= 0:
                    self._presence.get(room_token, {}).pop(device_id, None)
                if not self._presence.get(room_token):
                    self._presence.pop(room_token, None)

    def online_devices(self, room_token: str) -> list[str]:
        return list(self._presence.get(room_token, {}))

    async def publish(self, room_token: str, event: str, data: str) -> None:
        """Отправляет событие всем подписчикам комнаты.

        Многострочные данные разбиваются на отдельные строки ``data:``,
        иначе браузер обрезает событие на первой новой строке.
        """
        data_lines = "\n".join(f"data: {line}" for line in data.split("\n"))
        payload = f"event: {event}\n{data_lines}\n\n"
        async with self._lock:
            queues = list(self._subscribers.get(room_token, ()))
        for queue in queues:
            if queue.full():
                continue
            queue.put_nowait(payload)


hub = RoomHub()
