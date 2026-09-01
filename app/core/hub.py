import asyncio
from collections import defaultdict


class RoomHub:
    """In-memory pub/sub для рассылки sse-событий по комнатам."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def subscribe(self, room_token: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._subscribers[room_token].add(queue)
        return queue

    async def unsubscribe(self, room_token: str, queue: asyncio.Queue) -> None:
        async with self._lock:
            subscribers = self._subscribers.get(room_token)
            if subscribers is None:
                return
            subscribers.discard(queue)
            if not subscribers:
                self._subscribers.pop(room_token, None)

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
