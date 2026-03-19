from collections import defaultdict

QUEUE = defaultdict(list)

def add_to_queue(chat_id: int, item: dict):
    QUEUE[chat_id].append(item)
    return len(QUEUE[chat_id])

def get_queue(chat_id: int):
    return QUEUE.get(chat_id, [])

def pop_current(chat_id: int):
    if chat_id in QUEUE and QUEUE[chat_id]:
        return QUEUE[chat_id].pop(0)
    return None

def clear_queue(chat_id: int):
    QUEUE[chat_id] = []

def is_queue_empty(chat_id: int):
    return len(QUEUE.get(chat_id, [])) == 0
