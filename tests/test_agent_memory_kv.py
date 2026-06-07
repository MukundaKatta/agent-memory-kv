"""Standard-library unittest suite for agent-memory-kv.

Run with::

    python3 -m unittest discover -s tests
"""
import os
import sys
import tempfile
import time
import unittest

# Make the ``src`` layout package importable when running the suite directly
# with ``python -m unittest discover -s tests`` (no editable install required).
_SRC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"
)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from agent_memory_kv import AgentMemory, MemoryKeyError, _Entry


class AgentMemoryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self._dir.name, "mem.json")

    def tearDown(self) -> None:
        self._dir.cleanup()

    def mem(self) -> AgentMemory:
        return AgentMemory(self.path)

    # -- basic get/set --------------------------------------------------------

    def test_set_and_get(self):
        m = self.mem()
        m.set("name", "Alice")
        self.assertEqual(m.get("name"), "Alice")

    def test_get_missing_returns_default(self):
        m = self.mem()
        self.assertIsNone(m.get("missing"))
        self.assertEqual(m.get("missing", "fallback"), "fallback")

    def test_require_missing_raises(self):
        m = self.mem()
        with self.assertRaises(MemoryKeyError):
            m.require("nope")

    def test_require_existing(self):
        m = self.mem()
        m.set("x", 42)
        self.assertEqual(m.require("x"), 42)

    def test_has_true_false(self):
        m = self.mem()
        m.set("k", "v")
        self.assertTrue(m.has("k"))
        self.assertFalse(m.has("missing"))

    def test_delete(self):
        m = self.mem()
        m.set("k", "v")
        self.assertTrue(m.delete("k"))
        self.assertFalse(m.has("k"))

    def test_delete_missing(self):
        m = self.mem()
        self.assertFalse(m.delete("nope"))

    def test_keys(self):
        m = self.mem()
        m.set("a", 1)
        m.set("b", 2)
        self.assertEqual(sorted(m.keys()), ["a", "b"])

    def test_items(self):
        m = self.mem()
        m.set("a", 1)
        m.set("b", 2)
        self.assertEqual(dict(m.items()), {"a": 1, "b": 2})

    def test_to_dict(self):
        m = self.mem()
        m.set("x", {"nested": True})
        self.assertEqual(m.to_dict(), {"x": {"nested": True}})

    def test_clear(self):
        m = self.mem()
        m.set("a", 1)
        m.set("b", 2)
        self.assertEqual(m.clear(), 2)
        self.assertEqual(m.keys(), [])

    def test_len(self):
        m = self.mem()
        self.assertEqual(len(m), 0)
        m.set("x", 1)
        self.assertEqual(len(m), 1)

    def test_contains(self):
        m = self.mem()
        m.set("k", "v")
        self.assertIn("k", m)
        self.assertNotIn("missing", m)

    def test_overwrite_key(self):
        m = self.mem()
        m.set("k", "first")
        m.set("k", "second")
        self.assertEqual(m.get("k"), "second")

    def test_various_value_types(self):
        m = self.mem()
        m.set("int", 42)
        m.set("list", [1, 2, 3])
        m.set("dict", {"a": 1})
        m.set("bool", True)
        m.set("none", None)
        self.assertEqual(m.get("int"), 42)
        self.assertEqual(m.get("list"), [1, 2, 3])
        self.assertEqual(m.get("dict"), {"a": 1})
        self.assertIs(m.get("bool"), True)
        # A stored None is indistinguishable from a missing default of None,
        # but has() should still report the key as present.
        self.assertTrue(m.has("none"))

    # -- persistence ----------------------------------------------------------

    def test_persistence(self):
        m1 = self.mem()
        m1.set("persistent", "yes")
        m2 = self.mem()
        self.assertEqual(m2.get("persistent"), "yes")

    def test_persistence_creates_missing_parent_dirs(self):
        nested = os.path.join(self._dir.name, "a", "b", "c", "mem.json")
        m = AgentMemory(nested)
        m.set("k", "v")
        self.assertTrue(os.path.exists(nested))
        self.assertEqual(AgentMemory(nested).get("k"), "v")

    def test_corrupt_file_is_tolerated(self):
        with open(self.path, "w") as f:
            f.write("{ this is not valid json ]")
        m = self.mem()  # must not raise
        self.assertEqual(m.keys(), [])
        m.set("k", "v")
        self.assertEqual(m.get("k"), "v")

    def test_save_is_atomic_no_tmp_left_behind(self):
        m = self.mem()
        m.set("k", "v")
        leftover = [
            n for n in os.listdir(self._dir.name) if n.endswith(".tmp")
        ]
        self.assertEqual(leftover, [])

    # -- TTL ------------------------------------------------------------------

    def test_entry_is_expired(self):
        self.assertTrue(_Entry(value="x", expires_at=time.time() - 1).is_expired())

    def test_entry_no_ttl_never_expires(self):
        self.assertFalse(_Entry(value="x", expires_at=None).is_expired())

    def test_ttl_not_yet_expired(self):
        m = self.mem()
        m.set("k", "v", ttl=3600)
        self.assertEqual(m.get("k"), "v")
        self.assertTrue(m.has("k"))

    def test_ttl_expired_get_returns_default(self):
        m = self.mem()
        m.set("k", "v", ttl=0.01)
        time.sleep(0.05)
        self.assertIsNone(m.get("k"))
        self.assertFalse(m.has("k"))
        with self.assertRaises(MemoryKeyError):
            m.require("k")

    def test_ttl_rejects_non_positive(self):
        m = self.mem()
        with self.assertRaises(ValueError):
            m.set("k", "v", ttl=0)
        with self.assertRaises(ValueError):
            m.set("k", "v", ttl=-5)

    def test_ttl_survives_restart(self):
        """Regression: expiry must be wall-clock so it survives a new process.

        Previously expiry was stored using time.monotonic(), whose origin is
        per-process. A TTL persisted to disk and reloaded in a fresh instance
        would compare against an unrelated clock and expire (or persist)
        arbitrarily. With wall-clock expiry, a long TTL stays valid after
        reloading.
        """
        m1 = self.mem()
        m1.set("k", "v", ttl=3600)
        # Simulate a restart by constructing a brand-new instance from disk.
        m2 = self.mem()
        self.assertEqual(m2.get("k"), "v")
        self.assertTrue(m2.has("k"))

    def test_expired_entry_dropped_on_reload(self):
        m1 = self.mem()
        m1.set("k", "v", ttl=0.01)
        time.sleep(0.05)
        m2 = self.mem()
        self.assertNotIn("k", m2.keys())

    def test_prune_expired(self):
        m = self.mem()
        m.set("good", "yes")
        with m._lock:
            m._data["expired_key"] = _Entry(
                value="v", expires_at=time.time() - 100
            )
        self.assertEqual(m.prune_expired(), 1)
        self.assertNotIn("expired_key", m.keys())
        self.assertIn("good", m.keys())

    def test_prune_expired_nothing_to_do(self):
        m = self.mem()
        m.set("good", "yes")
        self.assertEqual(m.prune_expired(), 0)

    def test_expired_key_excluded_from_views(self):
        m = self.mem()
        m.set("good", "yes")
        with m._lock:
            m._data["bad"] = _Entry(value="v", expires_at=time.time() - 1)
        self.assertEqual(m.keys(), ["good"])
        self.assertEqual(dict(m.items()), {"good": "yes"})
        self.assertEqual(m.to_dict(), {"good": "yes"})
        self.assertEqual(len(m), 1)
        self.assertNotIn("bad", m)


if __name__ == "__main__":
    unittest.main()
