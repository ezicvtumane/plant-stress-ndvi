import time
import tracemalloc
import logging
from functools import wraps

logger = logging.getLogger("Profiler")

def profile_performance(func):
    """Легковесный декоратор для профилирования RAM и CPU времени."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        start_time = time.perf_counter()
        
        try:
            result = func(*args, **kwargs)
        finally:
            end_time = time.perf_counter()
            current, peak = tracemalloc.get_traced_memory()
            logger.info(
                f"[PROFILER] {func.__name__} | "
                f"Время: {(end_time - start_time)*1000:.2f} мс | "
                f"Пик RAM: {peak / 1024 / 1024:.2f} МБ"
            )
        return result
    return wrapper
