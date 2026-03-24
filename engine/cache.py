"""
TMOS13 Cache — Redis Integration

Redis-backed session caching and rate limiting.
Falls back to in-memory when Redis is unavailable.
Provides session persistence across server restarts.
"""
import json
import time
import logging
from typing import Optional
from collections import defaultdict

logger = logging.getLogger("tmos13.cache")


class RedisCache:
    """Redis-backed cache for sessions, rate limiting, and general KV storage."""

    def __init__(self, redis_url: str, prefix: str = "tmos13:"):
        self.prefix = prefix
        self._redis = None

        if redis_url:
            try:
                import redis
                self._redis = redis.from_url(redis_url, decode_responses=True)
                self._redis.ping()
                logger.info(f"Redis cache connected: {redis_url}")
            except Exception as e:
                logger.warning(f"Redis unavailable ({e}) — falling back to in-memory cache")
                self._redis = None
        else:
            logger.info("Redis not configured — using in-memory cache")

        # In-memory fallback
        self._mem_cache: dict[str, str] = {}
        self._mem_expiry: dict[str, float] = {}

    @property
    def enabled(self) -> bool:
        return self._redis is not None

    def _key(self, key: str) -> str:
        return f"{self.prefix}{key}"

    # ─── Core KV Operations ──────────────────────────────

    def get(self, key: str) -> Optional[str]:
        """Get a value by key."""
        if self._redis:
            return self._redis.get(self._key(key))
        else:
            k = self._key(key)
            if k in self._mem_expiry and time.time() > self._mem_expiry[k]:
                self._mem_cache.pop(k, None)
                self._mem_expiry.pop(k, None)
                return None
            return self._mem_cache.get(k)

    def set(self, key: str, value: str, ttl_seconds: int = 3600) -> None:
        """Set a value with optional TTL."""
        if self._redis:
            self._redis.setex(self._key(key), ttl_seconds, value)
        else:
            k = self._key(key)
            self._mem_cache[k] = value
            self._mem_expiry[k] = time.time() + ttl_seconds

    def delete(self, key: str) -> None:
        """Delete a key."""
        if self._redis:
            self._redis.delete(self._key(key))
        else:
            k = self._key(key)
            self._mem_cache.pop(k, None)
            self._mem_expiry.pop(k, None)

    def exists(self, key: str) -> bool:
        """Check if a key exists."""
        if self._redis:
            return self._redis.exists(self._key(key)) > 0
        else:
            k = self._key(key)
            if k in self._mem_expiry and time.time() > self._mem_expiry[k]:
                return False
            return k in self._mem_cache

    # ─── JSON Helpers ────────────────────────────────────

    def get_json(self, key: str) -> Optional[dict]:
        """Get and deserialize JSON value."""
        val = self.get(key)
        if val:
            return json.loads(val)
        return None

    def set_json(self, key: str, value: dict, ttl_seconds: int = 3600) -> None:
        """Serialize and set JSON value."""
        self.set(key, json.dumps(value), ttl_seconds)

    # ─── Rate Limiting ───────────────────────────────────

    def check_rate_limit(self, identifier: str, max_requests: int = 60,
                         window_seconds: int = 60) -> bool:
        """
        Sliding window rate limiter.
        Returns True if the request should be REJECTED, False if allowed.
        """
        key = f"rate:{identifier}"

        if self._redis:
            now = time.time()
            pipe = self._redis.pipeline()
            full_key = self._key(key)

            # Remove old entries
            pipe.zremrangebyscore(full_key, 0, now - window_seconds)
            # Add current request
            pipe.zadd(full_key, {str(now): now})
            # Count requests in window
            pipe.zcard(full_key)
            # Set expiry on the key
            pipe.expire(full_key, window_seconds)

            results = pipe.execute()
            count = results[2]
            return count > max_requests
        else:
            # In-memory fallback
            now = time.time()
            window_start = now - window_seconds
            mem_key = self._key(key)

            if mem_key not in self._mem_cache:
                self._mem_cache[mem_key] = "[]"

            timestamps = json.loads(self._mem_cache[mem_key])
            timestamps = [t for t in timestamps if t > window_start]

            if len(timestamps) >= max_requests:
                self._mem_cache[mem_key] = json.dumps(timestamps)
                return True

            timestamps.append(now)
            self._mem_cache[mem_key] = json.dumps(timestamps)
            return False

    # ─── Session Caching ─────────────────────────────────

    def cache_session(self, session_id: str, state_dict: dict, ttl: int = 3600) -> None:
        """Cache serialized session state."""
        self.set_json(f"session:{session_id}", state_dict, ttl)

    def get_cached_session(self, session_id: str) -> Optional[dict]:
        """Retrieve cached session state."""
        return self.get_json(f"session:{session_id}")

    def delete_session(self, session_id: str) -> None:
        """Remove a session from cache."""
        self.delete(f"session:{session_id}")

    def list_sessions(self) -> list[str]:
        """List all cached session IDs."""
        if self._redis:
            pattern = self._key("session:*")
            keys = self._redis.keys(pattern)
            prefix_len = len(self._key("session:"))
            return [k[prefix_len:] for k in keys]
        else:
            prefix = self._key("session:")
            return [k[len(prefix):] for k in self._mem_cache if k.startswith(prefix)]

    # ─── Protocol Caching ────────────────────────────────

    def cache_protocol(self, protocol_name: str, content: str, ttl: int = 86400) -> None:
        """Cache a loaded protocol file."""
        self.set(f"protocol:{protocol_name}", content, ttl)

    def get_cached_protocol(self, protocol_name: str) -> Optional[str]:
        """Get cached protocol content."""
        return self.get(f"protocol:{protocol_name}")

    def invalidate_protocols(self) -> None:
        """Clear all cached protocols."""
        if self._redis:
            keys = self._redis.keys(self._key("protocol:*"))
            if keys:
                self._redis.delete(*keys)
        else:
            to_remove = [k for k in self._mem_cache if k.startswith(self._key("protocol:"))]
            for k in to_remove:
                self._mem_cache.pop(k, None)

    # ─── Stats ───────────────────────────────────────────

    def get_stats(self) -> dict:
        """Get cache statistics."""
        if self._redis:
            info = self._redis.info("memory")
            return {
                "backend": "redis",
                "connected": True,
                "used_memory": info.get("used_memory_human", "unknown"),
                "keys": self._redis.dbsize(),
            }
        else:
            return {
                "backend": "memory",
                "connected": False,
                "keys": len(self._mem_cache),
            }

    # ─── Cleanup ─────────────────────────────────────────

    def flush(self) -> None:
        """Clear all cached data (use with caution)."""
        if self._redis:
            keys = self._redis.keys(self._key("*"))
            if keys:
                self._redis.delete(*keys)
        else:
            self._mem_cache.clear()
            self._mem_expiry.clear()


# ─── Module State ───────────────────────────────────────

_cache: Optional[RedisCache] = None


def init_cache(redis_url: str = "", prefix: str = "tmos13:") -> RedisCache:
    global _cache
    _cache = RedisCache(redis_url, prefix)
    return _cache


def get_cache() -> RedisCache:
    if _cache is None:
        raise RuntimeError("Cache not initialized")
    return _cache
