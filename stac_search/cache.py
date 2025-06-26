"""
Caching module for STAC Natural Query - handles various caching strategies
"""

import asyncio
import logging
from functools import wraps

from cachetools.keys import hashkey
from cachetools import TTLCache

logger = logging.getLogger(__name__)


geocoding_cache = TTLCache(maxsize=100, ttl=86400)  # 24 hours - locations don't change
embedding_cache = TTLCache(maxsize=100, ttl=86400)  # 24 hours - embeddings are stable
agent_cache = TTLCache(maxsize=100, ttl=3600)  # 1 hour - agent results cache


def _freeze(obj):
    if isinstance(obj, dict):
        # sort items to make order deterministic
        return frozenset((k, _freeze(v)) for k, v in sorted(obj.items()))
    if isinstance(obj, (list, tuple)):
        return tuple(_freeze(v) for v in obj)
    if isinstance(obj, set):
        return frozenset(_freeze(v) for v in obj)
    return obj  # assume primitive (int, str, etc.)


def async_cached(cache):
    lock = asyncio.Lock()

    def decorator(fn):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            # freeze each arg/kwarg
            fargs = tuple(_freeze(a) for a in args)
            fkwargs = {k: _freeze(v) for k, v in kwargs.items()}
            key = hashkey(f"{fn.__name__}", *fargs, **fkwargs)
            if key in cache:
                return cache[key]
            async with lock:
                if key in cache:
                    return cache[key]
                result = await fn(*args, **kwargs)
                cache[key] = result
                return result

        return wrapper

    return decorator


def clear_all_caches():
    """
    Clear all caches
    """
    logger.info("Clearing all caches")
    geocoding_cache.clear()
    embedding_cache.clear()
    agent_cache.clear()
