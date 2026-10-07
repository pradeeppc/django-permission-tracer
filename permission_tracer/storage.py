"""
Trace storage. Both backends add a trace without a read-modify-write cycle, so
concurrent requests can't drop each other's traces.
"""

import threading
from collections import deque

from django.core.cache import cache

from . import conf


class MemoryStore:
    """Per-process ring buffer. Fine for runserver; each worker sees only its own traces."""

    def __init__(self, max_traces):
        self._traces = deque(maxlen=max_traces)
        self._lock = threading.Lock()

    def add(self, trace):
        with self._lock:
            self._traces.appendleft(trace)

    def list(self, limit):
        with self._lock:
            return list(self._traces)[:limit]

    def count(self):
        return len(self._traces)

    def clear(self):
        with self._lock:
            self._traces.clear()


class CacheStore:
    """Ring buffer in Django's cache, shared between workers (use Redis/Memcached)."""

    SEQ_KEY = "permission_tracer:seq"
    SLOT_KEY = "permission_tracer:trace:{}"

    def __init__(self, max_traces, timeout):
        self.max_traces = max_traces
        self.timeout = timeout

    def add(self, trace):
        cache.add(self.SEQ_KEY, 0, timeout=None)
        try:
            seq = cache.incr(self.SEQ_KEY)
        except ValueError:  # key evicted between add() and incr()
            cache.set(self.SEQ_KEY, 1, timeout=None)
            seq = 1
        cache.set(self.SLOT_KEY.format(seq % self.max_traces), trace, timeout=self.timeout)

    def list(self, limit):
        seq = cache.get(self.SEQ_KEY) or 0
        count = min(limit, self.max_traces, seq)
        keys = [self.SLOT_KEY.format(n % self.max_traces) for n in range(seq, seq - count, -1)]
        found = cache.get_many(keys)
        return [found[k] for k in keys if k in found]

    def count(self):
        return min(cache.get(self.SEQ_KEY) or 0, self.max_traces)

    def clear(self):
        cache.delete_many(
            [self.SEQ_KEY] + [self.SLOT_KEY.format(n) for n in range(self.max_traces)]
        )


_store = None
_store_config = None
_lock = threading.Lock()


def get_store():
    global _store, _store_config
    config = (conf.get("STORAGE_BACKEND"), conf.get("MAX_TRACES"), conf.get("TRACE_TIMEOUT"))
    with _lock:
        if _store is None or config != _store_config:
            backend, max_traces, timeout = config
            if backend == "cache":
                _store = CacheStore(max_traces, timeout)
            elif backend == "memory":
                _store = MemoryStore(max_traces)
            else:
                raise ValueError(
                    "PERMISSION_TRACER['STORAGE_BACKEND'] must be 'memory' or 'cache', "
                    f"got {backend!r}"
                )
            _store_config = config
        return _store
