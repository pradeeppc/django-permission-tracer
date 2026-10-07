from django.core.cache import cache

from permission_tracer.storage import CacheStore, MemoryStore


def test_memory_store_is_bounded_and_newest_first():
    store = MemoryStore(3)
    for n in range(5):
        store.add({"n": n})
    assert [t["n"] for t in store.list(10)] == [4, 3, 2]


def test_cache_store_ring_buffer():
    cache.clear()
    store = CacheStore(3, timeout=60)
    for n in range(5):
        store.add({"n": n})
    assert [t["n"] for t in store.list(10)] == [4, 3, 2]
    assert store.count() == 3
    store.clear()
    assert store.list(10) == []
