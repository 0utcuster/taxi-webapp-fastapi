# app/realtime.py
import asyncio
import json
from typing import AsyncIterator

class _Hub:
    def __init__(self) -> None:
        self._queue: "asyncio.Queue[str]" = asyncio.Queue()

    async def publish(self, event: str, payload: dict) -> None:
        """
        Положить событие в очередь SSE.
        """
        data = json.dumps(payload, ensure_ascii=False)
        # формат SSE: event: <name>\ndata: <json>\n\n
        msg = f"event: {event}\ndata: {data}\n\n"
        await self._queue.put(msg)

    async def subscribe(self) -> AsyncIterator[str]:
        """
        Асинхронный генератор сообщений SSE.
        """
        while True:
            msg = await self._queue.get()
            yield msg

hub = _Hub()