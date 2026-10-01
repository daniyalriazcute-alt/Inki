from __future__ import annotations

from collections import deque


class ConversationMemory:
    """Small session-scoped short-term conversation buffer."""

    def __init__(self, max_turns: int = 8):
        self.max_turns = max_turns
        self._turns = deque(maxlen=max_turns * 2)

    def add(self, role: str, content: str) -> None:
        self._turns.append({"role": role, "content": content[:6000]})

    def as_text(self) -> str:
        if not self._turns:
            return ""
        return "\n".join(
            f"{turn['role'].upper()}: {turn['content']}" for turn in self._turns
        )

    def clear(self) -> None:
        self._turns.clear()
