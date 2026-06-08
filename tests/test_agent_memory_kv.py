import time
import pytest
from agent_memory_kv import AgentMemory, MemoryKeyError


@pytest.fixture
def tmp_path_mem(tmp_path):
    return str(tmp_path / "mem.json")


def test_set_and_get(tmp_path_mem):
    mem = AgentMemory(tmp_path_mem)
    mem.set("name", "Alice")
    assert mem.get("name") == "Alice"


def test_get_missing_returns_default(tmp_path_mem):
    mem = AgentMemory(tmp_path_mem)
    assert mem.get("missing") is None
    assert mem.get("missing", "fallback") == "fallback"


def test_require_missing_raises(tmp_path_mem):
    mem = AgentMemory(tmp_path_mem)
    with pytest.raises(MemoryKeyError):
        mem.require("nope")


def test_require_existing(tmp_path_mem):
    mem = AgentMemory(tmp_path_mem)
    mem.set("x", 42)
    assert mem.require("x") == 42


def test_has_true_false(tmp_path_mem):
    mem = AgentMemory(tmp_path_mem)
    mem.set("k", "v")
    assert mem.has("k")
    assert not mem.has("missing")


def test_delete(tmp_path_mem):
    mem = AgentMemory(tmp_path_mem)
    mem.set("k", "v")
    result = mem.delete("k")
    assert result is True
    assert not mem.has("k")


def test_delete_missing(tmp_path_mem):
    mem = AgentMemory(tmp_path_mem)
    assert mem.delete("nope") is False


def test_keys(tmp_path_mem):
    mem = AgentMemory(tmp_path_mem)
    mem.set("a", 1)
    mem.set("b", 2)
    assert sorted(mem.keys()) == ["a", "b"]


def test_items(tmp_path_mem):
    mem = AgentMemory(tmp_path_mem)
    mem.set("a", 1)
    mem.set("b", 2)
    items = dict(mem.items())
    assert items == {"a": 1, "b": 2}


def test_to_dict(tmp_path_mem):
    mem = AgentMemory(tmp_path_mem)
    mem.set("x", {"nested": True})
    assert mem.to_dict() == {"x": {"nested": True}}


def test_clear(tmp_path_mem):
    mem = AgentMemory(tmp_path_mem)
    mem.set("a", 1)
    mem.set("b", 2)
    count = mem.clear()
    assert count == 2
    assert mem.keys() == []


def test_len(tmp_path_mem):
    mem = AgentMemory(tmp_path_mem)
    assert len(mem) == 0
    mem.set("x", 1)
    assert len(mem) == 1


def test_contains(tmp_path_mem):
    mem = AgentMemory(tmp_path_mem)
    mem.set("k", "v")
    assert "k" in mem
    assert "missing" not in mem


def test_persistence(tmp_path_mem):
    mem1 = AgentMemory(tmp_path_mem)
    mem1.set("persistent", "yes")

    mem2 = AgentMemory(tmp_path_mem)
    assert mem2.get("persistent") == "yes"


def test_ttl_expire(tmp_path_mem):
    # Inject an entry whose wall-clock expiry is already in the past.
    from agent_memory_kv import _Entry

    e = _Entry(value="x", expires_at=time.time() - 1)
    assert e.is_expired()


def test_no_ttl_never_expires(tmp_path_mem):
    from agent_memory_kv import _Entry

    e = _Entry(value="x", expires_at=None)
    assert not e.is_expired()


def test_prune_expired(tmp_path_mem):
    mem = AgentMemory(tmp_path_mem)
    mem.set("good", "yes")
    # Manually inject an expired entry
    from agent_memory_kv import _Entry

    with mem._lock:
        mem._data["expired_key"] = _Entry(value="v", expires_at=time.time() - 100)
    pruned = mem.prune_expired()
    assert pruned == 1
    assert "expired_key" not in mem.keys()
    assert "good" in mem.keys()


def test_overwrite_key(tmp_path_mem):
    mem = AgentMemory(tmp_path_mem)
    mem.set("k", "first")
    mem.set("k", "second")
    assert mem.get("k") == "second"


def test_set_with_ttl_expires(tmp_path_mem):
    mem = AgentMemory(tmp_path_mem)
    mem.set("temp", "value", ttl=0.05)
    assert mem.get("temp") == "value"
    time.sleep(0.1)
    assert mem.get("temp") is None
    assert not mem.has("temp")


def test_ttl_survives_persistence(tmp_path_mem):
    # A future expiry must remain valid after reloading from disk (a new
    # process/instance), and a past expiry must read as expired. This exercises
    # the wall-clock semantics required for a persistent store.
    mem1 = AgentMemory(tmp_path_mem)
    mem1.set("long_lived", "ok", ttl=3600)
    mem2 = AgentMemory(tmp_path_mem)
    assert mem2.get("long_lived") == "ok"
    assert mem2.has("long_lived")

    mem1.set("short_lived", "gone", ttl=0.05)
    time.sleep(0.1)
    mem3 = AgentMemory(tmp_path_mem)
    assert mem3.get("short_lived") is None


def test_various_value_types(tmp_path_mem):
    mem = AgentMemory(tmp_path_mem)
    mem.set("int", 42)
    mem.set("list", [1, 2, 3])
    mem.set("dict", {"a": 1})
    mem.set("bool", True)
    assert mem.get("int") == 42
    assert mem.get("list") == [1, 2, 3]
    assert mem.get("dict") == {"a": 1}
    assert mem.get("bool") is True
