from __future__ import annotations

import os
import time
from collections import defaultdict
from threading import Lock


DEFAULT_CHAT_LIMIT = int(os.environ.get("RATE_LIMIT_CHAT_PER_MINUTE", "30"))
DEFAULT_ADMIN_LIMIT = int(os.environ.get("RATE_LIMIT_ADMIN_PER_MINUTE", "60"))
WINDOW_SECONDS = 60


class _TokenBucket:
    def __init__(self, rate: int, burst: int | None = None):
        self.rate = rate
        self.burst = burst or rate
        self.tokens = float(self.burst)
        self.last_refill = time.monotonic()

    def consume(self, n: int = 1) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(float(self.burst), self.tokens + elapsed * (self.rate / WINDOW_SECONDS))
        self.last_refill = now
        if self.tokens >= n:
            self.tokens -= n
            return True
        return False


class RateLimiter:
    def __init__(self):
        self._lock = Lock()
        self._buckets: dict[str, _TokenBucket] = {}

    def _key(self, identifier: str, prefix: str) -> str:
        return "{}:{}".format(prefix, identifier)

    def allow(self, identifier: str, prefix: str, rate: int) -> bool:
        key = self._key(identifier, prefix)
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None or bucket.rate != rate:
                bucket = _TokenBucket(rate)
                self._buckets[key] = bucket
            return bucket.consume(1)

    def cleanup(self) -> None:
        pass


_global_limiter = RateLimiter()


def check_rate_limit(ip: str, path: str, user_id: str = "") -> tuple[bool, dict[str, object]]:
    if path.startswith("/api/admin/"):
        key = "{}-{}".format(ip, user_id) if user_id else ip
        allowed = _global_limiter.allow(key, "admin", DEFAULT_ADMIN_LIMIT)
        return allowed, {
            "limit": DEFAULT_ADMIN_LIMIT,
            "window": "{}s".format(WINDOW_SECONDS),
            "category": "admin",
        }
    elif path.startswith("/api/gaokao/chat"):
        key = "{}-{}".format(ip, user_id) if user_id else ip
        allowed = _global_limiter.allow(key, "chat", DEFAULT_CHAT_LIMIT)
        return allowed, {
            "limit": DEFAULT_CHAT_LIMIT,
            "window": "{}s".format(WINDOW_SECONDS),
            "category": "chat",
        }
    return True, {}
