import time
from collections import defaultdict

TTL_SECONDS = 3600  # conversations expire after 1 hour of inactivity
MAX_HISTORY = 20    # max messages to keep per conversation


class ConversationManager:
    def __init__(self):
        self._store: dict[str, dict] = defaultdict(lambda: {"messages": [], "last_active": 0})

    def get_history(self, phone: str) -> list[dict]:
        entry = self._store[phone]
        if time.time() - entry["last_active"] > TTL_SECONDS:
            entry["messages"] = []
        return list(entry["messages"])

    def add_turn(self, phone: str, user_text: str, assistant_text: str):
        entry = self._store[phone]
        entry["messages"].append({"role": "user", "content": user_text})
        entry["messages"].append({"role": "assistant", "content": assistant_text})
        if len(entry["messages"]) > MAX_HISTORY * 2:
            entry["messages"] = entry["messages"][-MAX_HISTORY * 2:]
        entry["last_active"] = time.time()

    def clear(self, phone: str):
        self._store[phone] = {"messages": [], "last_active": 0}
