import threading
from collections import deque


class ActionQueue:
    """Bounded FIFO; rejecting a full queue is explicit, never silently unbounded."""

    def __init__(self, capacity=8):
        if type(capacity) is not int or capacity <= 0:
            raise ValueError("Pojemność kolejki musi być dodatnim int.")
        self.capacity = capacity
        self._items = deque()
        self._lock = threading.Lock()
        self._available = threading.Event()

    def put(self, request):
        with self._lock:
            if len(self._items) >= self.capacity or any(
                x.token == request.token for x in self._items
            ):
                return False
            self._items.append(request)
            self._available.set()
            return True

    def pop(self):
        with self._lock:
            result = self._items.popleft() if self._items else None
            if not self._items:
                self._available.clear()
            return result

    def clear(self):
        with self._lock:
            items = tuple(self._items)
            self._items.clear()
            self._available.clear()
            return items

    def __len__(self):
        with self._lock:
            return len(self._items)

    def wait(self, timeout=0.1):
        return self._available.wait(timeout)

