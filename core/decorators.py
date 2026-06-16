from __future__ import annotations

import asyncio
import functools
import time

from core.errors.logging import ExceptionLogging
from core.loggers import log_tasks


class TaskDecorator:
    @staticmethod
    def task(action_name: str, log: bool = None):
        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                start_time = time.perf_counter()
                try:
                    result = await func(*args, **kwargs)
                    time_elapsed = round((time.perf_counter() - start_time), 2)
                    if time_elapsed > 3:
                        log_tasks.warning(
                            f"{action_name} took a long time to complete and finished in {time_elapsed}s"
                        )
                    elif log:
                        log_tasks.info(f"{action_name} completed in {time_elapsed}s")
                    return result
                except Exception as error:
                    ExceptionLogging.log_exception(
                        log_tasks,
                        error,
                        bot_name="Tickets",
                        component=action_name,
                        extra={"elapsed_s": round((time.perf_counter() - start_time), 2)},
                    )
                    raise error

            return wrapper

        return decorator
