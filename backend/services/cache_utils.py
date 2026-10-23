"""Simple TTL cache for expensive API/GEE queries."""
import time
from typing import Any, Callable, Optional


_cache: dict[str, tuple[float, Any]] = {}


def get_cached(key: str, ttl_seconds: int) -> Optional[Any]:
    entry = _cache.get(key)
    if entry is None:
        return None
    expires_at, value = entry
    if time.time() > expires_at:
        del _cache[key]
        return None
    return value


def set_cached(key: str, value: Any, ttl_seconds: int) -> None:
    _cache[key] = (time.time() + ttl_seconds, value)


def cached_fetch(key: str, ttl_seconds: int, fetch_fn: Callable[[], Any]) -> Any:
    cached = get_cached(key, ttl_seconds)
    if cached is not None:
        return cached
    value = fetch_fn()
    set_cached(key, value, ttl_seconds)
    return value


def clear_cache(prefix: Optional[str] = None) -> int:
    if prefix is None:
        count = len(_cache)
        _cache.clear()
        return count
    keys = [k for k in _cache if k.startswith(prefix)]
    for k in keys:
        del _cache[k]
    return len(keys)
