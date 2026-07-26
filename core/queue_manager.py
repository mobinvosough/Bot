import asyncio
from collections import deque
from loguru import logger


class QueueManager:
    def __init__(self):
        self._queue: deque = deque()
        self._processing = False

    def enqueue(self, item):
        self._queue.append(item)
        logger.info("Item added to queue, size: {}", len(self._queue))

    def dequeue(self):
        if self._queue:
            return self._queue.popleft()
        return None

    @property
    def size(self) -> int:
        return len(self._queue)

    @property
    def is_empty(self) -> bool:
        return len(self._queue) == 0

    def clear(self):
        self._queue.clear()
        logger.info("Queue cleared")
