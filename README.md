# agent-memory-kv

Persistent key-value memory for agents backed by a JSON file, with optional per-key TTL.

## Install

```
pip install agent-memory-kv
```

## Usage

```python
from agent_memory_kv import AgentMemory

mem = AgentMemory("/tmp/agent-001.json")
mem.set("user_name", "Alice")
mem.set("session_topic", "Python", ttl=3600)  # expires in 1 hour

val = mem.get("user_name")       # "Alice"
mem.has("user_name")             # True
mem.require("missing_key")       # raises MemoryKeyError

print(mem.keys())
print(mem.to_dict())
mem.prune_expired()              # remove expired entries
mem.delete("user_name")
```
