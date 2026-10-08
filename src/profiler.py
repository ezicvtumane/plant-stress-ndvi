import os
import time
import resource
import logging
from functools import wraps
import asyncio

logger = logging.getLogger("Profiler")
PROFILE_ENABLED = os.environ.get("AGY_PROFILE", "0") == "1"

def profile_performance(func):
    """Zero-overhead декоратор профилирования. Включается через AGY_PROFILE=1."""
    if not PROFILE_ENABLED:
        return func

    if asyncio.iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            start_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            try:
                return await func(*args, **kwargs)
            finally:
                elapsed = (time.perf_counter() - start_time) * 1000
                end_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                delta_rss = (end_rss - start_rss) / 1024.0 # on Linux ru_maxrss is in KB
                logger.info(f"[PROFILER] {func.__name__} (async) | Время: {elapsed:.2f} мс | RSS пик: {end_rss/1024.0:.2f} МБ (Δ {delta_rss:.2f} МБ)")
        return async_wrapper
    else:
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            start_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            try:
                return func(*args, **kwargs)
            finally:
                elapsed = (time.perf_counter() - start_time) * 1000
                end_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                delta_rss = (end_rss - start_rss) / 1024.0
                logger.info(f"[PROFILER] {func.__name__} | Время: {elapsed:.2f} мс | RSS пик: {end_rss/1024.0:.2f} МБ (Δ {delta_rss:.2f} МБ)")
        return sync_wrapper
