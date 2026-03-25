from collections import defaultdict, deque
from typing import Union

from bot.helpers import Media, Track

QueueItem = Union[Media, Track]


class Queue:
    def __init__(self):
        self.queues: dict[int, deque[QueueItem]] = defaultdict(deque)

    def add(self, chat_id: int, item: QueueItem) -> int:
        self.queues[chat_id].append(item)
        return len(self.queues[chat_id]) - 1

    def check_item(self, chat_id: int, item_id: str) -> tuple[int, QueueItem | None]:
        position, item = next(
            (
                (index, item)
                for index, item in enumerate(list(self.queues[chat_id]))
                if item.id == item_id
            ),
            (-1, None),
        )
        return position, item

    def force_add(
        self,
        chat_id: int,
        item: QueueItem,
        remove: int | bool = False,
    ) -> None:
        self.remove_current(chat_id)
        self.queues[chat_id].appendleft(item)

        if remove:
            self.queues[chat_id].rotate(-remove)
            self.queues[chat_id].popleft()
            self.queues[chat_id].rotate(remove)

    def get_current(self, chat_id: int) -> QueueItem | None:
        return self.queues[chat_id][0] if self.queues[chat_id] else None

    def get_next(self, chat_id: int, check: bool = False) -> QueueItem | None:
        if not self.queues[chat_id]:
            return None

        if check:
            return self.queues[chat_id][1] if len(self.queues[chat_id]) > 1 else None

        self.queues[chat_id].popleft()
        return self.queues[chat_id][0] if self.queues[chat_id] else None

    def get_queue(self, chat_id: int) -> list[QueueItem]:
        return list(self.queues[chat_id])

    def remove_current(self, chat_id: int) -> None:
        if self.queues[chat_id]:
            self.queues[chat_id].popleft()

    def clear(self, chat_id: int) -> None:
        self.queues[chat_id].clear()
