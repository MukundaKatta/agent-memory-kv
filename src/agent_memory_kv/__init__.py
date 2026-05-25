"""
agent-memory-kv: Persistent key-value memory for agents, backed by a JSON file.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from dataclasses import dataclass
from typing import Any, Optional


class MemoryKeyError(KeyError):
    """Raised when a key is not found in memory."""


@dataclass
class _Entry:
    value: Any
    expires_at: Optional[float]  # monotonic time, None = never

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.monotonic() >= self.expires_at


class AgentMemory:
    """
    Persistent key-value store for agent memory.

    Values survive process restarts (backed by a JSON file).
    Supports optional per-key TTL expiry.

    Usage::

        mem = AgentMemory("/tmp/agent-001.json")
        mem.set("user_name", "Alice")
        mem.set("session_topic", "Python", ttl=3600)
        val = mem.get("user_name")       # "Alice"
        mem.has("user_name")             # True
        mem.delete("user_name")
        mem.keys()                       # list of non-expired keys
    """

    def __init__(self, path: str) -> None:
        self._path = os.path.expanduser(path)
        self._lock = threading.Lock()
        self._data: dict[str, _Entry] = {}
        self._load()

    # -- persistence ----------------------------------------------------------

    def _load(self) -> None:
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path) as f:
                raw = json.load(f)
            for k, v in raw.items():
                self._data[k] = _Entry(
                    value=v["value"],
                    expires_at=v.get("expires_at"),
                )
        except (json.JSONDecodeError, KeyError, OSError):
            self._data = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        raw = {
            k: {"value": e.value, "expires_at": e.expires_at}
            for k, e in self._data.items()
            if not e.is_expired()
        }
        fd, tmp = tempfile.mkstemp(
            dir=os.path.dirname(self._path) or ".", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(raw, f)
            os.replace(tmp, self._path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    # -- public API -----------------------------------------------------------

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Set a key. ttl is seconds from now; None = never expires."""
        expires_at = (time.monotonic() + ttl) if ttl is not None else None
        with self._lock:
            self._data[key] = _Entry(value=value, expires_at=expires_at)
            self._save()

    def get(self, key: str, default: Any = None) -> Any:
        """Return value for key, or default if missing/expired."""
        with self._lock:
            entry = self._data.get(key)
            if entry is None or entry.is_expired():
                return default
            return entry.value

    def require(self, key: str) -> Any:
        """Return value or raise MemoryKeyError if missing/expired."""
        with self._lock:
            entry = self._data.get(key)
            if entry is None or entry.is_expired():
                raise MemoryKeyError(key)
            return entry.value

    def has(self, key: str) -> bool:
        with self._lock:
            entry = self._data.get(key)
            return entry is not None and not entry.is_expired()

    def delete(self, key: str) -> bool:
        """Delete key. Returns True if it existed."""
        with self._lock:
            existed = key in self._data
            self._data.pop(key, None)
            if existed:
                self._save()
            return existed

    def keys(self) -> list[str]:
        """Return all non-expired keys."""
        with self._lock:
            return [k for k, e in self._data.items() if not e.is_expired()]

    def items(self) -> list[tuple[str, Any]]:
        """Return all non-expired (key, value) pairs."""
        with self._lock:
            return [(k, e.value) for k, e in self._data.items() if not e.is_expired()]

    def to_dict(self) -> dict[str, Any]:
        return dict(self.items())

    def clear(self) -> int:
        """Delete all keys. Returns count deleted."""
        with self._lock:
            count = len(self._data)
            self._data.clear()
            self._save()
            return count

    def prune_expired(self) -> int:
        """Remove expired keys. Returns count removed."""
        with self._lock:
            expired = [k for k, e in self._data.items() if e.is_expired()]
            for k in expired:
                del self._data[k]
            if expired:
                self._save()
            return len(expired)

    def __len__(self) -> int:
        return len(self.keys())

    def __contains__(self, key: str) -> bool:
        return self.has(key)


__all__ = ["AgentMemory", "MemoryKeyError"]
