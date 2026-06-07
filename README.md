# agent-memory-kv

[![CI](https://github.com/MukundaKatta/agent-memory-kv/actions/workflows/ci.yml/badge.svg)](https://github.com/MukundaKatta/agent-memory-kv/actions/workflows/ci.yml)

Persistent key-value memory for agents, backed by a single JSON file, with
optional per-key TTL.

It's a tiny, dependency-free building block for giving an LLM agent (or any
long-running process) memory that **survives restarts**. You give it a file
path; it gives you a dict-like store whose contents are written to disk on
every change and reloaded automatically next time.

## Features

- **Zero dependencies** — pure standard library, works on Python 3.9+.
- **Persistent** — every write is flushed to a JSON file and reloaded on init.
- **Atomic writes** — saves go to a temp file then `os.replace`, so a crash
  mid-write can't corrupt your data.
- **Per-key TTL** — set an expiry in seconds; expired keys are skipped on read
  and dropped on save. TTLs are stored as absolute timestamps, so they are
  honored correctly even after the process restarts.
- **Thread-safe** — all operations are guarded by an internal lock.
- **Dict-like ergonomics** — `len(mem)`, `key in mem`, `mem.to_dict()`.
- **Typed** — ships with inline type hints and a `py.typed` marker.

## Install

```bash
pip install agent-memory-kv
```

Or from source:

```bash
git clone https://github.com/MukundaKatta/agent-memory-kv
cd agent-memory-kv
pip install -e .
```

## Usage

```python
from agent_memory_kv import AgentMemory, MemoryKeyError

# Point it at a file. Parent directories are created on first write.
mem = AgentMemory("/tmp/agent-001.json")

# Store values (any JSON-serializable type).
mem.set("user_name", "Alice")
mem.set("preferences", {"theme": "dark", "lang": "en"})

# Store a value that expires in one hour.
mem.set("session_topic", "Python", ttl=3600)

# Read with a default for missing/expired keys.
mem.get("user_name")            # "Alice"
mem.get("missing", "fallback")  # "fallback"

# Read but raise if missing/expired.
mem.require("user_name")        # "Alice"
try:
    mem.require("missing")
except MemoryKeyError:
    ...

# Membership and counts (dict-like).
mem.has("user_name")            # True
"user_name" in mem              # True
len(mem)                        # number of non-expired keys

# Bulk views (expired keys excluded).
mem.keys()                      # ["user_name", "preferences", "session_topic"]
mem.items()                     # [("user_name", "Alice"), ...]
mem.to_dict()                   # {"user_name": "Alice", ...}

# Maintenance.
mem.prune_expired()             # remove expired entries, returns count removed
mem.delete("user_name")         # returns True if the key existed
mem.clear()                     # delete everything, returns count removed
```

Because the store is persistent, a fresh instance pointed at the same path sees
the same data:

```python
AgentMemory("/tmp/agent-001.json").set("seen", True)
assert AgentMemory("/tmp/agent-001.json").get("seen") is True
```

## API

`AgentMemory(path: str)` — open (or create) a store backed by `path`. `~` is
expanded; parent directories are created lazily on the first write.

| Method | Description |
| --- | --- |
| `set(key, value, ttl=None)` | Store `value` under `key`. `ttl` is seconds-from-now (must be positive); `None` never expires. Persists immediately. |
| `get(key, default=None)` | Return the value, or `default` if the key is missing or expired. |
| `require(key)` | Return the value, or raise `MemoryKeyError` if missing/expired. |
| `has(key)` | `True` if the key exists and is not expired. |
| `delete(key)` | Remove the key; returns `True` if it existed. |
| `keys()` | List of non-expired keys. |
| `items()` | List of non-expired `(key, value)` pairs. |
| `to_dict()` | Plain `dict` of non-expired pairs. |
| `clear()` | Remove all keys; returns the number removed. |
| `prune_expired()` | Drop expired keys from disk; returns the number removed. |
| `len(mem)` | Number of non-expired keys. |
| `key in mem` | Equivalent to `mem.has(key)`. |

`MemoryKeyError` — subclass of `KeyError`, raised by `require()`.

### Notes & limitations

- Values must be JSON-serializable (str, int, float, bool, None, list, dict).
- A stored `None` is indistinguishable from a missing key when read via
  `get()` (both return the default). Use `has()` to disambiguate.
- The whole store is rewritten on each mutating call, so this is best suited to
  small-to-medium memory (hundreds/thousands of keys), not high-throughput data.

## Development

Run the test suite with the standard library — no extra dependencies needed:

```bash
python -m unittest discover -s tests -v
```

## License

MIT
