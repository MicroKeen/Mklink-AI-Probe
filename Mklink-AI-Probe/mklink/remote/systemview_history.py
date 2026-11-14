"""Bounded trace history with incremental time/count eviction.

The manager's history lock protects this collection. Arrival order and capture
sequence are independent of timestamps: metadata and out-of-order times must
not turn time eviction into a prefix-only operation.
"""
from collections import OrderedDict
import heapq
import math


class SystemViewHistory:
    def __init__(self):
        self._events = OrderedDict()
        self._times = OrderedDict()
        self._heap = []
        self._nan = set()
        self._sequence = 0

    def __len__(self):
        return len(self._events)

    def __iter__(self):
        return iter(self._events.values())

    def __reversed__(self):
        return reversed(self._events.values())

    def clear(self):
        self._events.clear()
        self._times.clear()
        self._heap.clear()
        self._nan.clear()
        self._sequence = 0

    def _index_time(self, key, event):
        value = event.get('t_us')
        if isinstance(value, (int, float)):
            self._times[key] = value
            if isinstance(value, float) and math.isnan(value):
                self._nan.add(key)
            else:
                heapq.heappush(self._heap, (value, key))

    def append(self, event):
        self._sequence += 1
        self._events[self._sequence] = event
        self._index_time(self._sequence, event)

    def reindex_times(self):
        """Time fields can be filled once after a CPU-clock hint arrives."""
        self._times.clear()
        self._heap.clear()
        self._nan.clear()
        for key, event in self._events.items():
            self._index_time(key, event)

    def _remove(self, key):
        self._events.pop(key, None)
        self._times.pop(key, None)
        self._nan.discard(key)

    def trim(self, *, max_count, window_us):
        if window_us > 0 and self._times:
            cutoff = next(reversed(self._times.values())) - window_us
            if math.isnan(cutoff):
                # Preserve the previous >= cutoff semantics even for malformed
                # non-finite timestamps; untimed metadata remains readable.
                for key in list(self._times):
                    self._remove(key)
                self._heap.clear()
            else:
                for key in list(self._nan):
                    self._remove(key)
                while self._heap and self._heap[0][0] < cutoff:
                    _, key = heapq.heappop(self._heap)
                    self._remove(key)
        while len(self._events) > max_count:
            self._remove(next(iter(self._events)))
        # Count eviction leaves lazy timestamp entries. Bound those entries
        # without rescanning retained history on every producer batch.
        if len(self._heap) > 2 * len(self._times) + 1024:
            self._heap = [(value, key) for key, value in self._times.items()
                          if key not in self._nan]
            heapq.heapify(self._heap)
